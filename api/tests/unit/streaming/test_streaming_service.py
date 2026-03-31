"""Testes unitários do StreamingService."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vms.streaming.domain import StreamSession
from vms.streaming.service import StreamingService, _parse_path


class TestStreamingService:
    """Testes do StreamingService — sessões de streaming."""

    @pytest.fixture
    def repo(self):
        """Mock do repositório de sessões."""
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda s: s)
        repo.end_session = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def svc(self, repo):
        """StreamingService com repo mockado."""
        return StreamingService(repo)

    async def test_on_stream_ready_valid_path(self, svc, repo):
        """Path válido cria sessão de streaming."""
        result = await svc.on_stream_ready("tenant-t1/cam-c1")
        assert result is not None
        assert result.tenant_id == "t1"
        assert result.camera_id == "c1"
        assert result.mediamtx_path == "tenant-t1/cam-c1"
        repo.create.assert_called_once()

    async def test_on_stream_ready_invalid_path(self, svc, repo):
        """Path inválido retorna None sem criar sessão."""
        result = await svc.on_stream_ready("invalid-path")
        assert result is None
        repo.create.assert_not_called()

    async def test_on_stream_stopped_active_session(self, svc, repo):
        """Encerra sessão ativa existente."""
        ended = StreamSession(
            id="s1", tenant_id="t1", camera_id="c1",
            mediamtx_path="tenant-t1/cam-c1",
        )
        ended.end()
        repo.end_session = AsyncMock(return_value=ended)

        result = await svc.on_stream_stopped("tenant-t1/cam-c1")
        assert result is not None
        assert result.ended_at is not None
        repo.end_session.assert_called_once_with("tenant-t1/cam-c1")

    async def test_on_stream_stopped_no_active(self, svc, repo):
        """Sem sessão ativa, retorna None."""
        result = await svc.on_stream_stopped("tenant-t1/cam-c1")
        assert result is None

    async def test_verify_publish_token_valid(self, svc):
        """Path válido + token não-vazio = permitido."""
        result = await svc.verify_publish_token(
            "tenant-t1/cam-c1", "some-token"
        )
        assert result is True

    async def test_verify_publish_token_empty_token(self, svc):
        """Token vazio = negado."""
        result = await svc.verify_publish_token("tenant-t1/cam-c1", "")
        assert result is False

    async def test_verify_publish_token_invalid_path(self, svc):
        """Path inválido = negado."""
        result = await svc.verify_publish_token("bad-path", "token")
        assert result is False


class TestParsePath:
    """Testes do helper _parse_path."""

    def test_valid_path(self):
        """Path correto retorna (tenant_id, camera_id)."""
        result = _parse_path("tenant-abc/cam-123")
        assert result == ("abc", "123")

    def test_invalid_path(self):
        """Path inválido retorna None."""
        assert _parse_path("invalid") is None

    def test_path_with_uuid(self):
        """Path com UUIDs funciona."""
        result = _parse_path("tenant-a1b2c3/cam-d4e5f6")
        assert result == ("a1b2c3", "d4e5f6")
