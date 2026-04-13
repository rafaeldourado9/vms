"""
Testes unitários das entidades enriquecidas (Sprint A3).

Cobre:
- Camera: factories, transições de estado, Domain Events
- RecordingSegment: factory from_file_path, is_expired, verify_integrity
- Clip: máquina de estado, validações
- VODStream: máquina de estado, validações

Estrutura: Given-When-Then (AAA)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from vms.cameras.domain import (
    Camera,
    CameraActivated,
    CameraAnalyticsDisabled,
    CameraAnalyticsEnableded,
    CameraDeactivated,
    CameraManufacturer,
    StreamProtocol,
    StreamQuality,
)
from vms.recordings.domain import (
    Clip,
    ClipFailed,
    ClipReady,
    ClipRequested,
    ClipStatus,
    RecordingSegment,
    SegmentIndexed,
)
from vms.shared.exceptions import BusinessRuleViolation, StateTransitionError
from vms.shared.kernel import CameraId, EntityId, RecordingId, TenantId, VODStreamId
from vms.shared.value_objects import Sha256Hash
from vms.vod.domain import (
    VODStream,
    VODStreamCreated,
    VODStreamFailed,
    VODStreamGenerationStarted,
    VODStreamReady,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId.new()


@pytest.fixture
def camera_id() -> CameraId:
    return CameraId.new()


@pytest.fixture
def agent_id() -> EntityId:
    return EntityId.new()


@pytest.fixture
def recording_id() -> RecordingId:
    return RecordingId.new()


@pytest.fixture
def vod_stream_id() -> VODStreamId:
    return VODStreamId.new()


# ─── Testes: Camera Factories ────────────────────────────────────────────────

class TestCameraFactories:
    """Testes das factories de Camera."""

    def test_create_rtmp_push(self, tenant_id: TenantId):
        # When
        camera = Camera.create_rtmp_push(
            tenant_id=tenant_id,
            name="Entrada Principal",
        )

        # Then
        assert camera.tenant_id == tenant_id
        assert camera.name == "Entrada Principal"
        assert camera.stream_protocol == StreamProtocol.RTMP_PUSH
        assert camera.rtmp_stream_key is not None
        assert len(camera.rtmp_stream_key) > 20  # token_urlsafe(32)
        assert camera.agent_id is None
        assert camera.is_active is True
        assert camera.is_online is False
        assert camera.ia_enabled is False

    def test_create_rtsp_pull(self, tenant_id: TenantId, agent_id: EntityId):
        # When
        camera = Camera.create_rtsp_pull(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Portaria Norte",
            rtsp_url="rtsp://192.168.1.100:554/stream",
        )

        # Then
        assert camera.tenant_id == tenant_id
        assert camera.agent_id == agent_id
        assert camera.stream_protocol == StreamProtocol.RTSP_PULL
        assert camera.rtsp_url == "rtsp://192.168.1.100:554/stream"
        assert camera.rtmp_stream_key is None

    def test_rtmp_push_emits_created_event(self, tenant_id: TenantId):
        # When
        camera = Camera.create_rtmp_push(
            tenant_id=tenant_id,
            name="Camera 01",
        )

        # Then
        events = camera.pull_events()
        # Factory não emite evento por padrão (só transições de estado)
        assert len(events) == 0


# ─── Testes: Camera State Transitions ────────────────────────────────────────

class TestCameraStateTransitions:
    """Testes de transições de estado da Camera."""

    def test_go_online_emits_event(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.pull_events()  # clear any initial events

        # When
        camera.go_online()

        # Then
        assert camera.is_online is True
        assert camera.last_seen_at is not None
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraActivated)
        assert events[0].camera_id == camera.id

    def test_go_online_fails_if_inactive(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.deactivate()

        # Then
        with pytest.raises(BusinessRuleViolation, match="inativa não pode ficar online"):
            camera.go_online()

    def test_go_offline_emits_event(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.go_online()
        camera.pull_events()  # limpa events anteriores

        # When
        camera.go_offline()

        # Then
        assert camera.is_online is False
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraDeactivated)

    def test_go_offline_idempotent(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        assert camera.is_online is False

        # When
        camera.go_offline()  # chamada redundante

        # Then
        assert camera.is_online is False
        events = camera.pull_events()
        assert len(events) == 0  # Nenhum evento novo (idempotente)

    def test_activate(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.deactivate()
        camera.pull_events()  # clear deactivate events

        # When
        camera.activate()

        # Then
        assert camera.is_active is True
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraActivated)

    def test_deactivate_clears_online_and_analytics(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.go_online()
        camera.enable_analytics()
        camera.pull_events()

        # When
        camera.deactivate()

        # Then
        assert camera.is_active is False
        assert camera.is_online is False
        assert camera.ia_enabled is False
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraDeactivated)

    def test_enable_analytics(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # When
        camera.enable_analytics()

        # Then
        assert camera.ia_enabled is True
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraAnalyticsEnableded)

    def test_enable_analytics_fails_if_inactive(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.deactivate()

        # Then
        with pytest.raises(BusinessRuleViolation, match="inativa não pode ter analytics"):
            camera.enable_analytics()

    def test_disable_analytics(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")
        camera.enable_analytics()
        camera.pull_events()

        # When
        camera.disable_analytics()

        # Then
        assert camera.ia_enabled is False
        events = camera.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], CameraAnalyticsDisabled)


# ─── Testes: Camera Properties ───────────────────────────────────────────────

class TestCameraProperties:
    """Testes de propriedades calculadas da Camera."""

    def test_mediamtx_path_rtmp_push(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # Then
        assert camera.mediamtx_path.startswith("live/")
        assert camera.rtmp_stream_key in camera.mediamtx_path

    def test_mediamtx_path_rtsp_pull(self, tenant_id: TenantId, agent_id: EntityId):
        # Given
        camera = Camera.create_rtsp_pull(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Cam 01",
            rtsp_url="rtsp://192.168.1.100/stream",
        )

        # Then
        assert camera.mediamtx_path == f"tenant-{tenant_id}/cam-{camera.id}"

    def test_has_location(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # Then (inicialmente sem localização)
        assert camera.has_location is False

        # When
        camera.update_location(latitude=-23.5505, longitude=-46.6333)

        # Then
        assert camera.has_location is True

    def test_is_rtmp_push(self, tenant_id: TenantId):
        # Given
        camera_rtmp = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam RTMP")
        camera_rtsp = Camera.create_rtsp_pull(
            tenant_id=tenant_id,
            agent_id=EntityId.new(),
            name="Cam RTSP",
            rtsp_url="rtsp://192.168.1.100/stream",
        )

        # Then
        assert camera_rtmp.is_rtmp_push is True
        assert camera_rtsp.is_rtmp_push is False

    def test_is_agent_based(self, tenant_id: TenantId, agent_id: EntityId):
        # Given
        camera_rtmp = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam RTMP")
        camera_rtsp = Camera.create_rtsp_pull(
            tenant_id=tenant_id,
            agent_id=agent_id,
            name="Cam RTSP",
            rtsp_url="rtsp://192.168.1.100/stream",
        )

        # Then
        assert camera_rtmp.is_agent_based is False
        assert camera_rtsp.is_agent_based is True


# ─── Testes: Camera Location ─────────────────────────────────────────────────

class TestCameraLocation:
    """Testes de atualização de localização."""

    def test_update_location_valid(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # When
        camera.update_location(
            latitude=-23.5505,
            longitude=-46.6333,
            address="São Paulo, SP",
        )

        # Then
        assert camera.latitude == -23.5505
        assert camera.longitude == -46.6333
        assert camera.address == "São Paulo, SP"

    def test_update_location_invalid_latitude(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # Then
        with pytest.raises(BusinessRuleViolation, match="Latitude inválida"):
            camera.update_location(latitude=91.0, longitude=-46.6333)

    def test_update_location_invalid_longitude(self, tenant_id: TenantId):
        # Given
        camera = Camera.create_rtmp_push(tenant_id=tenant_id, name="Cam 01")

        # Then
        with pytest.raises(BusinessRuleViolation, match="Longitude inválida"):
            camera.update_location(latitude=-23.5505, longitude=-181.0)


# ─── Testes: RecordingSegment ────────────────────────────────────────────────

class TestRecordingSegment:
    """Testes de RecordingSegment."""

    def test_from_file_path_parses_timestamp(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        file_path = "/recordings/tenant-abc/cam-xyz/2026/04/12/10-00-00.mp4"

        # When
        segment = RecordingSegment.from_file_path(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="tenant-abc/cam-xyz",
            file_path=file_path,
        )

        # Then
        assert segment.started_at.year == 2026
        assert segment.started_at.month == 4
        assert segment.started_at.day == 12
        assert segment.started_at.hour == 10
        assert segment.started_at.minute == 0
        assert segment.started_at.second == 0
        assert segment.duration_seconds == 60.0

    def test_is_expired(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given - segment from more than 2 years ago (well beyond 365 day retention)
        past_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        segment = RecordingSegment(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="test",
            file_path="/test.mp4",
            started_at=past_time,
            ended_at=past_time,
            duration_seconds=60.0,
            size_bytes=1000000,
        )

        # Then
        assert segment.is_expired(retention_days=7) is True
        assert segment.is_expired(retention_days=365) is True

    def test_is_not_expired(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        now = datetime.now(timezone.utc)
        segment = RecordingSegment(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="test",
            file_path="/test.mp4",
            started_at=now,
            ended_at=now,
            duration_seconds=60.0,
            size_bytes=1000000,
        )

        # Then
        assert segment.is_expired(retention_days=7) is False

    def test_verify_integrity_match(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        stored_hash = Sha256Hash("a" * 64)
        segment = RecordingSegment(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="test",
            file_path="/test.mp4",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            duration_seconds=60.0,
            size_bytes=1000000,
            sha256_hash=stored_hash,
        )
        current_hash = Sha256Hash("a" * 64)

        # When
        is_valid = segment.verify_integrity(current_hash)

        # Then
        assert is_valid is True

    def test_verify_integrity_mismatch(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        stored_hash = Sha256Hash("a" * 64)
        segment = RecordingSegment(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="test",
            file_path="/test.mp4",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
            duration_seconds=60.0,
            size_bytes=1000000,
            sha256_hash=stored_hash,
        )
        current_hash = Sha256Hash("b" * 64)

        # When
        is_valid = segment.verify_integrity(current_hash)

        # Then
        assert is_valid is False

    def test_covers_time(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        start = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 12, 10, 1, 0, tzinfo=timezone.utc)
        segment = RecordingSegment(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path="test",
            file_path="/test.mp4",
            started_at=start,
            ended_at=end,
            duration_seconds=60.0,
            size_bytes=1000000,
        )

        # Then
        mid = datetime(2026, 4, 12, 10, 0, 30, tzinfo=timezone.utc)
        assert segment.covers_time(mid) is True
        assert segment.covers_time(start) is True
        assert segment.covers_time(end) is True
        assert segment.covers_time(datetime(2026, 4, 12, 9, 0, 0, tzinfo=timezone.utc)) is False


# ─── Testes: Clip State Machine ──────────────────────────────────────────────

class TestClipStateMachine:
    """Testes da máquina de estado do Clip."""

    def test_create_valid_clip(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)

        # When
        clip = Clip(
            id=recording_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            starts_at=starts,
            ends_at=ends,
        )

        # Then
        assert clip.status == ClipStatus.PENDING
        assert clip.duration_seconds == 300.0  # 5 minutos

    def test_create_clip_invalid_time_range(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)  # ends < starts

        # Then
        with pytest.raises(BusinessRuleViolation, match="ends_at deve ser posterior a starts_at"):
            Clip(
                id=recording_id,
                tenant_id=tenant_id,
                camera_id=camera_id,
                starts_at=starts,
                ends_at=ends,
            )

    def test_start_processing(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)

        # When
        clip.start_processing()

        # Then
        assert clip.status == ClipStatus.PROCESSING
        events = clip.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], ClipRequested)

    def test_start_processing_fails_if_not_pending(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)
        clip.start_processing()

        # Then
        with pytest.raises(StateTransitionError, match="Não é possível iniciar processamento"):
            clip.start_processing()

    def test_mark_ready(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)
        clip.start_processing()
        clip.pull_events()  # clear start_processing events

        # When
        clip.mark_ready("/path/to/clip.mp4")

        # Then
        assert clip.status == ClipStatus.READY
        assert clip.file_path == "/path/to/clip.mp4"
        assert clip.is_ready is True
        events = clip.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], ClipReady)
        assert events[0].file_path == "/path/to/clip.mp4"

    def test_mark_ready_fails_if_not_processing(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)

        # Then
        with pytest.raises(StateTransitionError, match="Esperado: processing"):
            clip.mark_ready("/path/to/clip.mp4")

    def test_mark_failed(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)
        clip.start_processing()
        clip.pull_events()  # clear start_processing events

        # When
        clip.mark_failed("ffmpeg falhou")

        # Then
        assert clip.status == ClipStatus.FAILED
        assert clip.error == "ffmpeg falhou"
        assert clip.is_ready is False
        events = clip.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], ClipFailed)
        assert events[0].error == "ffmpeg falhou"

    def test_full_lifecycle(self, tenant_id: TenantId, camera_id: CameraId, recording_id: RecordingId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        clip = Clip(id=recording_id, tenant_id=tenant_id, camera_id=camera_id, starts_at=starts, ends_at=ends)

        # When
        clip.start_processing()
        clip.pull_events()
        clip.mark_ready("/path/to/clip.mp4")
        events = clip.pull_events()

        # Then
        assert clip.status == ClipStatus.READY
        assert len(events) == 1
        assert isinstance(events[0], ClipReady)


# ─── Testes: VODStream State Machine ─────────────────────────────────────────

class TestVODStreamStateMachine:
    """Testes da máquina de estado do VODStream."""

    def test_create_valid_stream(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)

        # When
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4", "/path/seg2.mp4"],
            started_at=starts,
            ended_at=ends,
        )

        # Then
        assert stream.status == "pending"
        assert stream.segment_count == 2
        assert stream.duration_seconds == 300.0
        assert stream.is_ready is False

    def test_create_stream_fails_without_segments(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)

        # Then
        with pytest.raises(BusinessRuleViolation, match="pelo menos um segmento"):
            VODStream.create(
                id=vod_stream_id,
                tenant_id=tenant_id,
                camera_id=camera_id,
                segments=[],
                started_at=starts,
                ended_at=ends,
            )

    def test_start_generation(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )

        # When
        stream.start_generation()

        # Then
        assert stream.status == "generating"
        assert stream.is_generating is True
        events = stream.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], VODStreamGenerationStarted)

    def test_start_generation_fails_if_not_pending(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )
        stream.start_generation()

        # Then
        with pytest.raises(StateTransitionError, match="Esperado: pending"):
            stream.start_generation()

    def test_mark_ready(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )
        stream.start_generation()
        stream.pull_events()  # clear start_generation events

        # When
        stream.mark_ready("/tmp/vod/playlist.m3u8")

        # Then
        assert stream.status == "ready"
        assert stream.playlist_path == "/tmp/vod/playlist.m3u8"
        assert stream.is_ready is True
        events = stream.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], VODStreamReady)
        assert events[0].playlist_path == "/tmp/vod/playlist.m3u8"

    def test_mark_ready_fails_if_not_generating(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )

        # Then
        with pytest.raises(StateTransitionError, match="Esperado: generating"):
            stream.mark_ready("/tmp/vod/playlist.m3u8")

    def test_mark_failed(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )
        stream.start_generation()
        stream.pull_events()  # clear start_generation events

        # When
        stream.mark_failed("ffmpeg error")

        # Then
        assert stream.status == "failed"
        assert stream.error == "ffmpeg error"
        assert stream.is_failed is True
        events = stream.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], VODStreamFailed)
        assert events[0].error == "ffmpeg error"

    def test_full_lifecycle(self, tenant_id: TenantId, camera_id: CameraId, vod_stream_id: VODStreamId):
        # Given
        starts = datetime(2026, 4, 12, 10, 0, 0, tzinfo=timezone.utc)
        ends = datetime(2026, 4, 12, 10, 5, 0, tzinfo=timezone.utc)
        stream = VODStream.create(
            id=vod_stream_id,
            tenant_id=tenant_id,
            camera_id=camera_id,
            segments=["/path/seg1.mp4"],
            started_at=starts,
            ended_at=ends,
        )

        # When
        stream.start_generation()
        stream.pull_events()
        stream.mark_ready("/tmp/vod/playlist.m3u8")
        events = stream.pull_events()

        # Then
        assert stream.status == "ready"
        assert len(events) == 1
        assert isinstance(events[0], VODStreamReady)
