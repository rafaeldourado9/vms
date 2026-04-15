"""Testes de domínio de gravações — RecordingSegment e Clip."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from vms.recordings.domain import (
    Clip,
    ClipStatus,
    RecordingSegment,
    SegmentIndexed,
    ClipRequested,
    ClipReady,
    ClipFailed,
)
from vms.shared.exceptions import BusinessRuleViolation, StateTransitionError
from vms.shared.kernel import CameraId, RecordingId, TenantId
from vms.shared.value_objects import Sha256Hash


# ─── RecordingSegment ────────────────────────────────────────────────────────


class TestRecordingSegment:
    """Testes da entidade RecordingSegment."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    @pytest.fixture
    def camera_id(self):
        return CameraId(uuid.uuid4())

    @pytest.fixture
    def segment(self, tenant_id, camera_id):
        return RecordingSegment(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-1/cam-abc",
            file_path="/recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4",
            started_at=datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc),
            duration_seconds=60.0,
            size_bytes=1048576,
        )

    def test_create_segment(self, segment):
        """Segmento criado com valores corretos."""
        assert segment.duration_seconds == 60.0
        assert segment.size_bytes == 1048576
        assert segment.analytics_processed is False
        assert segment.custody_chain == []

    def test_from_file_path_parses_timestamp(self, tenant_id, camera_id):
        """Factory from_file_path extrai timestamp do path."""
        segment = RecordingSegment.from_file_path(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-1/cam-abc",
            file_path="/recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4",
        )
        assert segment.started_at == datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)

    def test_from_file_path_corrects_double_extension(self, tenant_id, camera_id):
        """Factory corrige double extension .mp4.mp4."""
        segment = RecordingSegment.from_file_path(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-1/cam-abc",
            file_path="/recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4.mp4",
        )
        assert segment.file_path.endswith(".mp4")
        assert not segment.file_path.endswith(".mp4.mp4")

    def test_from_file_path_ensures_leading_slash(self, tenant_id, camera_id):
        """Factory garante path absoluto."""
        segment = RecordingSegment.from_file_path(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-1/cam-abc",
            file_path="recordings/tenant-1/cam-abc/2026/04/12/10-00-00.mp4",
        )
        assert segment.file_path.startswith("/")

    def test_is_expired_true(self, segment):
        """is_expired retorna True se passado retention_days."""
        # Segmento de 2026, retenção de 1 dia → expirado
        assert segment.is_expired(retention_days=1) is True

    def test_is_expired_false(self, tenant_id, camera_id):
        """is_expired retorna False se dentro de retention_days."""
        now = datetime.now(timezone.utc)
        fresh_segment = RecordingSegment(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-1/cam-abc",
            file_path="/recordings/segment.mp4",
            started_at=now,
            ended_at=now + timedelta(seconds=60),
            duration_seconds=60.0,
            size_bytes=1024,
        )
        assert fresh_segment.is_expired(retention_days=7) is False

    def test_verify_integrity_match(self, segment):
        """verify_integrity retorna True quando hashes coincidem."""
        test_hash = Sha256Hash("a" * 64)
        segment.sha256_hash = test_hash
        assert segment.verify_integrity(test_hash) is True

    def test_verify_integrity_mismatch(self, segment):
        """verify_integrity retorna False quando hashes diferem."""
        segment.sha256_hash = Sha256Hash("a" * 64)
        current = Sha256Hash("b" * 64)
        assert segment.verify_integrity(current) is False

    def test_verify_integrity_no_stored_hash(self, segment):
        """verify_integrity retorna False se não há hash armazenado."""
        assert segment.sha256_hash is None
        assert segment.verify_integrity(Sha256Hash("c" * 64)) is False

    def test_covers_time_true(self, segment):
        """covers_time retorna True para timestamp dentro do segmento."""
        ts = datetime(2026, 4, 12, 10, 0, 30, tzinfo=timezone.utc)
        assert segment.covers_time(ts) is True

    def test_covers_time_false_before(self, segment):
        """covers_time retorna False para timestamp antes do segmento."""
        ts = datetime(2026, 4, 12, 9, 59, 0, tzinfo=timezone.utc)
        assert segment.covers_time(ts) is False

    def test_covers_time_false_after(self, segment):
        """covers_time retorna False para timestamp depois do segmento."""
        ts = datetime(2026, 4, 12, 10, 2, 0, tzinfo=timezone.utc)
        assert segment.covers_time(ts) is False

    def test_mark_processed(self, segment):
        """mark_processed marca como processado para o plugin."""
        segment.mark_processed("intrusion_detection")
        assert segment.analytics_processed is True
        assert "intrusion_detection" in segment.analytics_plugins_processed
        assert segment.analytics_processed_at is not None

    def test_mark_processed_does_not_duplicate(self, segment):
        """mark_processed não duplica entrada de plugin."""
        segment.mark_processed("intrusion_detection")
        segment.mark_processed("intrusion_detection")
        count = segment.analytics_plugins_processed.count("intrusion_detection")
        assert count == 1

    def test_is_processed_for(self, segment):
        """is_processed_for verifica processamento por plugin."""
        assert segment.is_processed_for("intrusion_detection") is False
        segment.mark_processed("intrusion_detection")
        assert segment.is_processed_for("intrusion_detection") is True

    def test_add_custody_entry(self, segment):
        """add_custody_entry adiciona entrada na cadeia de custódia."""
        segment.add_custody_entry("viewed", "user-1", {"ip": "192.168.1.100"})
        assert len(segment.custody_chain) == 1
        entry = segment.custody_chain[0]
        assert entry["action"] == "viewed"
        assert entry["actor"] == "user-1"
        assert entry["ip"] == "192.168.1.100"
        assert "timestamp" in entry

    def test_custody_chain_is_append_only(self, segment):
        """Cadeia de custódia é append-only."""
        segment.add_custody_entry("viewed", "user-1")
        segment.add_custody_entry("downloaded", "user-2")
        segment.add_custody_entry("exported_forensic", "user-1")
        assert len(segment.custody_chain) == 3


# ─── Clip ────────────────────────────────────────────────────────────────────


class TestClip:
    """Testes da entidade Clip."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    @pytest.fixture
    def camera_id(self):
        return CameraId(uuid.uuid4())

    @pytest.fixture
    def clip(self, tenant_id, camera_id):
        now = datetime.now(timezone.utc)
        return Clip(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            starts_at=now,
            ends_at=now + timedelta(seconds=120),
        )

    def test_create_valid_clip(self, clip):
        """Clip criado com status PENDING."""
        assert clip.status == ClipStatus.PENDING
        assert clip.duration_seconds == 120.0

    def test_create_clip_invalid_time_range(self, tenant_id, camera_id):
        """Clip com ends_at <= starts_at lança BusinessRuleViolation."""
        now = datetime.now(timezone.utc)
        with pytest.raises(BusinessRuleViolation, match="ends_at deve ser posterior"):
            Clip(
                id=RecordingId(uuid.uuid4()),
                tenant_id=tenant_id,
                camera_id=camera_id,
                starts_at=now + timedelta(seconds=120),
                ends_at=now,
            )

    def test_start_processing(self, clip):
        """Transição pending → processing."""
        clip.start_processing()
        assert clip.status == ClipStatus.PROCESSING
        events = clip.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], ClipRequested)

    def test_start_processing_fails_if_not_pending(self, clip):
        """Não é possível iniciar de outro estado."""
        clip.status = ClipStatus.READY
        with pytest.raises(StateTransitionError, match="pending"):
            clip.start_processing()

    def test_mark_ready(self, clip):
        """Transição processing → ready."""
        clip.start_processing()
        clip.mark_ready("/path/to/clip.mp4")
        assert clip.status == ClipStatus.READY
        assert clip.file_path == "/path/to/clip.mp4"
        events = clip.pull_events()
        assert any(isinstance(e, ClipReady) for e in events)

    def test_mark_ready_fails_if_not_processing(self, clip):
        """Não é possível marcar ready de pending."""
        with pytest.raises(StateTransitionError, match="processing"):
            clip.mark_ready("/path/to/clip.mp4")

    def test_mark_failed(self, clip):
        """Transição pending → failed."""
        clip.mark_failed("timeout")
        assert clip.status == ClipStatus.FAILED
        assert clip.error == "timeout"
        events = clip.pull_events()
        assert any(isinstance(e, ClipFailed) for e in events)

    def test_mark_failed_from_processing(self, clip):
        """Transição processing → failed."""
        clip.start_processing()
        clip.mark_failed("disk full")
        assert clip.status == ClipStatus.FAILED
        assert clip.error == "disk full"

    def test_is_ready_property(self, clip):
        """is_ready retorna True apenas para status READY."""
        assert clip.is_ready is False
        clip.start_processing()
        assert clip.is_ready is False
        clip.mark_ready("/path/to/clip.mp4")
        assert clip.is_ready is True

    def test_full_clip_lifecycle(self, tenant_id, camera_id):
        """Ciclo de vida completo: pending → processing → ready."""
        now = datetime.now(timezone.utc)
        clip = Clip(
            id=RecordingId(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            starts_at=now,
            ends_at=now + timedelta(seconds=300),
        )
        assert clip.status == ClipStatus.PENDING

        clip.start_processing()
        assert clip.status == ClipStatus.PROCESSING

        clip.mark_ready("/path/to/clip.mp4")
        assert clip.status == ClipStatus.READY
        assert clip.is_ready is True
        assert clip.file_path == "/path/to/clip.mp4"
        assert clip.duration_seconds == 300.0
