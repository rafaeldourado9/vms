"""Testes de integração — câmeras RTMP push (configuração e auth)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestRtmpPushCamera:
    """Câmeras com protocolo RTMP push."""

    async def test_create_rtmp_camera_generates_stream_key(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Criação de câmera RTMP push gera stream_key automaticamente."""
        from unittest.mock import AsyncMock, patch

        with patch("vms.cameras.mediamtx.MediaMTXClient.add_path", new_callable=AsyncMock):
            resp = await client.post(
                "/api/v1/cameras",
                json={
                    "name": "Câmera RTMP Push",
                    "stream_protocol": "rtmp_push",
                },
                headers=auth_headers,
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["stream_protocol"] == "rtmp_push"
        assert data["rtmp_stream_key"] is not None
        assert len(data["rtmp_stream_key"]) > 8

    async def test_rtmp_config_endpoint(
        self, client: AsyncClient, auth_headers: dict
    ):
        """GET /cameras/{id}/rtmp-config retorna URL e stream key."""
        from unittest.mock import AsyncMock, patch

        # Cria câmera RTMP push
        with patch("vms.cameras.mediamtx.MediaMTXClient.add_path", new_callable=AsyncMock):
            create_resp = await client.post(
                "/api/v1/cameras",
                json={
                    "name": "RTMP Camera",
                    "stream_protocol": "rtmp_push",
                },
                headers=auth_headers,
            )
        assert create_resp.status_code == 201
        cam_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/cameras/{cam_id}/rtmp-config", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "rtmp_url" in data
        assert "stream_key" in data
        assert data["stream_key"] == create_resp.json()["rtmp_stream_key"]

    async def test_publish_auth_with_correct_stream_key(
        self, client: AsyncClient, auth_headers: dict
    ):
        """publish-auth aceita stream key gerada para câmera RTMP push."""
        from unittest.mock import AsyncMock, patch

        with patch("vms.cameras.mediamtx.MediaMTXClient.add_path", new_callable=AsyncMock):
            create_resp = await client.post(
                "/api/v1/cameras",
                json={
                    "name": "RTMP Auth Test",
                    "stream_protocol": "rtmp_push",
                },
                headers=auth_headers,
            )
        cam_data = create_resp.json()
        stream_key = cam_data["rtmp_stream_key"]
        cam_id = cam_data["id"]
        tenant_id = cam_data["tenant_id"]

        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": f"tenant-{tenant_id}/cam-{cam_id}",
                "query": f"key={stream_key}",
            },
        )
        assert resp.status_code == 200

    async def test_publish_auth_wrong_stream_key_rejected(
        self, client: AsyncClient, auth_headers: dict
    ):
        """publish-auth rejeita stream key incorreta."""
        from unittest.mock import AsyncMock, patch

        with patch("vms.cameras.mediamtx.MediaMTXClient.add_path", new_callable=AsyncMock):
            create_resp = await client.post(
                "/api/v1/cameras",
                json={
                    "name": "RTMP Wrong Key",
                    "stream_protocol": "rtmp_push",
                },
                headers=auth_headers,
            )
        cam_data = create_resp.json()
        cam_id = cam_data["id"]
        tenant_id = cam_data["tenant_id"]

        resp = await client.post(
            "/streaming/publish-auth",
            json={
                "action": "publish",
                "path": f"tenant-{tenant_id}/cam-{cam_id}",
                "query": "key=totally-wrong-key",
            },
        )
        assert resp.status_code == 401
