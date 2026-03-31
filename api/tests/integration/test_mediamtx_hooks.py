"""Testes de integração — webhooks MediaMTX e streaming auth."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestPublishAuth:
    """POST /streaming/publish-auth — autenticação de publicação MediaMTX."""

    @patch("vms.streaming.service.StreamingService.verify_publish_token", new_callable=AsyncMock, return_value=True)
    async def test_publish_auth_valid(self, _mock, client: AsyncClient):
        """Path válido + token válido aceita publicação (lógica de auth mockada)."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "token=abc123",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_publish_auth_no_token(self, client: AsyncClient):
        """Sem token rejeita publicação."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "",
            },
        )
        assert resp.status_code == 401

    async def test_publish_auth_invalid_path(self, client: AsyncClient):
        """Path inválido rejeita publicação."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "bad-path",
                "query": "token=abc123",
            },
        )
        assert resp.status_code == 401


class TestMediaMTXWebhooksIntegration:
    """Webhooks MediaMTX via events router — testes de integração."""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_on_ready_publishes_event(self, mock_pub, client: AsyncClient):
        """on_ready publica evento camera.online."""
        resp = await client.post(
            "/api/v1/webhooks/mediamtx/on_ready",
            json={"path": "tenant-t1/cam-c1"},
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "camera.online"

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_on_not_ready_publishes_event(self, mock_pub, client: AsyncClient):
        """on_not_ready publica evento camera.offline."""
        resp = await client.post(
            "/api/v1/webhooks/mediamtx/on_not_ready",
            json={"path": "tenant-t1/cam-c1"},
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "camera.offline"

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_segment_ready_publishes_event(self, mock_pub, client: AsyncClient):
        """segment_ready publica evento recording.segment_ready."""
        resp = await client.post(
            "/api/v1/webhooks/mediamtx/segment_ready",
            json={
                "path": "tenant-t1/cam-c1",
                "segment_path": "/recordings/seg001.mp4",
            },
        )
        assert resp.status_code == 200
        mock_pub.assert_called_once()
        assert mock_pub.call_args[0][0] == "recording.segment_ready"
