"""Testes unitários do RecordingService."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from vms.recordings.domain import Clip, ClipStatus, RecordingSegment
from vms.recordings.service import RecordingService, _resolve_ids


class TestRecordingService:
    """Testes do RecordingService."""

    @pytest.fixture
    def segment_repo(self):
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda s: s)
        repo.delete_older_than = AsyncMock(return_value=5)
        return repo

    @pytest.fixture
    def clip_repo(self):
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda c: c)
        return repo

    @pytest.fixture
    def svc(self, segment_repo, clip_repo):
        return RecordingService(segment_repo, clip_repo)

    async def test_index_segment(self, svc, segment_repo):
        """Indexação cria segmento com dados corretos."""
        with patch("vms.recordings.service._parse_file_metadata") as mock_meta:
            now = datetime.now(UTC)
            mock_meta.return_value = (
                now - timedelta(seconds=60), now, 60.0, 1024000,
            )
            result = await svc.index_segment(
                tenant_id="t1",
                camera_id="c1",
                file_path="/recordings/seg001.mp4",
                mediamtx_path="tenant-t1/cam-c1",
            )
            assert result.tenant_id == "t1"
            assert result.camera_id == "c1"
            assert result.duration_seconds == 60.0
            segment_repo.create.assert_called_once()

    async def test_cleanup_expired_segments(self, svc, segment_repo):
        """Cleanup remove segmentos e retorna contagem."""
        result = await svc.cleanup_expired_segments("t1", "c1", 7)
        assert result == 5
        segment_repo.delete_older_than.assert_called_once()

    async def test_create_clip(self, svc, clip_repo):
        """Criação de clip persiste no repo."""
        now = datetime.now(UTC)
        result = await svc.create_clip(
            "t1", "c1", now - timedelta(minutes=5), now,
        )
        assert result.tenant_id == "t1"
        assert result.status == ClipStatus.PENDING
        clip_repo.create.assert_called_once()


class TestResolveIds:
    """Testes do helper _resolve_ids."""

    def test_explicit_ids(self):
        t, c = _resolve_ids("tenant-x/cam-y", "t1", "c1")
        assert t == "t1"
        assert c == "c1"

    def test_parse_from_path(self):
        t, c = _resolve_ids("tenant-abc/cam-123", "", "")
        assert t == "abc"
        assert c == "123"

    def test_invalid_path_returns_originals(self):
        t, c = _resolve_ids("invalid-path", "t1", "c1")
        assert t == "t1"
        assert c == "c1"
