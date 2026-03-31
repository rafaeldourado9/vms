"""Testes unitários dos webhooks MediaMTX (streaming)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def streaming_client(app):
    """Client para testar webhooks MediaMTX."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMediaMTXOnReady:
    """POST /api/v1/webhooks/mediamtx/on_ready"""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_on_ready_valid_path(self, mock_pub, streaming_client):
        """Path válido publica evento camera.online."""
        resp = await streaming_client.post(
            "/api/v1/webhooks/mediamtx/on_ready",
            json={"path": "tenant-t1/cam-c1"},
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        call_args = mock_pub.call_args
        assert call_args[0][0] == "camera.online"

    async def test_on_ready_invalid_path(self, streaming_client):
        """Path inválido retorna ok mas não falha."""
        resp = await streaming_client.post(
            "/api/v1/webhooks/mediamtx/on_ready",
            json={"path": "invalid-path"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestMediaMTXOnNotReady:
    """POST /api/v1/webhooks/mediamtx/on_not_ready"""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_on_not_ready_valid_path(self, mock_pub, streaming_client):
        """Path válido publica evento camera.offline."""
        resp = await streaming_client.post(
            "/api/v1/webhooks/mediamtx/on_not_ready",
            json={"path": "tenant-t1/cam-c1"},
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "camera.offline"


class TestMediaMTXSegmentReady:
    """POST /api/v1/webhooks/mediamtx/segment_ready"""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_segment_ready(self, mock_pub, streaming_client):
        """Segmento pronto publica evento recording.segment_ready."""
        resp = await streaming_client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={
                "path": "tenant-t1/cam-c1",
                "segment_path": "/recordings/seg001.mp4",
            },
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "recording.segment_ready"
