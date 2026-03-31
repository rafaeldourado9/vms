"""Testes de integração — publish-auth com stream key RTMP push."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestRtmpPushAuth:
    """Autenticação publish-auth para câmeras RTMP push."""

    @patch("vms.streaming.service.StreamingService.verify_publish_token", new_callable=AsyncMock, return_value=True)
    async def test_rtmp_push_valid_stream_key(self, _mock, client: AsyncClient):
        """Stream key válida autoriza publicação RTMP."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "key=valid-stream-key",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    @patch("vms.streaming.service.StreamingService.verify_publish_token", new_callable=AsyncMock, return_value=False)
    async def test_rtmp_push_invalid_stream_key(self, _mock, client: AsyncClient):
        """Stream key inválida rejeita publicação RTMP."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "key=wrong-key",
            },
        )
        assert resp.status_code == 401

    async def test_rtmp_push_no_key(self, client: AsyncClient):
        """Sem stream key rejeita publicação RTMP."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "",
            },
        )
        assert resp.status_code == 401

    @patch("vms.streaming.service.StreamingService.verify_publish_token", new_callable=AsyncMock, return_value=True)
    async def test_agent_api_key_publish_allowed(self, _mock, client: AsyncClient):
        """Agent com API key válida pode publicar."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": "tenant-t1/cam-c1",
                "query": "token=vms_agent_key",
            },
        )
        assert resp.status_code == 200
        _mock.assert_called_once_with("tenant-t1/cam-c1", "vms_agent_key")
