"""Testes de integração — hook read-auth MediaMTX."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestReadAuth:
    """POST /streaming/read-auth e dispatch via publish-auth action=read."""

    @patch("vms.streaming.service.StreamingService.verify_viewer_token", new_callable=AsyncMock, return_value=True)
    async def test_read_auth_valid_token(self, _mock, client: AsyncClient):
        """Token de viewer válido autoriza leitura."""
        resp = await client.post(
            "/streaming/read-auth",
            json={
                "action": "read",
                "path": "tenant-t1/cam-c1",
                "query": "token=valid-viewer-jwt",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    async def test_read_auth_no_token(self, client: AsyncClient):
        """Sem token rejeita leitura."""
        resp = await client.post(
            "/streaming/read-auth",
            json={
                "action": "read",
                "path": "tenant-t1/cam-c1",
                "query": "",
            },
        )
        assert resp.status_code == 401

    @patch("vms.streaming.service.StreamingService.verify_viewer_token", new_callable=AsyncMock, return_value=True)
    async def test_publish_auth_dispatches_read_action(self, _mock, client: AsyncClient):
        """publish-auth com action=read delega para verify_viewer_token."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "read",
                "path": "tenant-t1/cam-c1",
                "query": "token=viewer-jwt",
            },
        )
        assert resp.status_code == 200
        _mock.assert_called_once()

    @patch("vms.streaming.service.StreamingService.verify_viewer_token", new_callable=AsyncMock, return_value=False)
    async def test_publish_auth_read_invalid_token_rejected(self, _mock, client: AsyncClient):
        """publish-auth com action=read e token inválido retorna 401."""
        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "read",
                "path": "tenant-t1/cam-c1",
                "query": "token=bad-token",
            },
        )
        assert resp.status_code == 401
