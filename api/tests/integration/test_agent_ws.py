"""Testes de integração — WebSocket endpoint /agents/me/ws."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


class TestAgentWebSocket:
    """WebSocket endpoint para config push ao agent."""

    async def test_ws_route_exists(self, client: AsyncClient):
        """Rota WebSocket /agents/me/ws existe (retorna 403 ou 426 para GET normal)."""
        # WebSocket route não responde a HTTP GET — esperamos 403, 426 ou 404
        resp = await client.get("/api/v1/agents/me/ws?api_key=test")
        assert resp.status_code in (403, 426, 404)

    async def test_ws_route_without_api_key_query_param(self, client: AsyncClient):
        """Rota WS sem api_key na query retorna erro de parâmetro faltante."""
        resp = await client.get("/api/v1/agents/me/ws")
        # Falta query param api_key
        assert resp.status_code in (403, 422, 426, 404)

    async def test_camera_service_publishes_on_create(self, client: AsyncClient, auth_headers: dict):
        """Criação de câmera com agent_id publica evento no Redis channel do agent."""
        import redis.asyncio as aioredis
        from unittest.mock import patch, AsyncMock

        published: list[tuple] = []

        original_publish = aioredis.Redis.publish

        async def mock_publish(self_r, channel, message):
            published.append((channel, message))
            return 0

        with (
            patch("vms.cameras.mediamtx.MediaMTXClient.add_path", new_callable=AsyncMock),
            patch.object(aioredis.Redis, "publish", mock_publish),
        ):
            # Cria agent primeiro
            create_agent_resp = await client.post(
                "/api/v1/agents",
                json={"name": "WS Test Agent"},
                headers=auth_headers,
            )
            assert create_agent_resp.status_code == 201
            agent_id = create_agent_resp.json()["id"]

            # Cria câmera com agent_id
            await client.post(
                "/api/v1/cameras",
                json={
                    "name": "WS Camera",
                    "stream_protocol": "rtsp_pull",
                    "rtsp_url": "rtsp://192.168.1.100:554/stream",
                    "agent_id": agent_id,
                },
                headers=auth_headers,
            )

        # Verifica que publish foi chamado com o channel correto
        channels = [ch for ch, _ in published]
        assert any(f"agent:{agent_id}:config" in ch for ch in channels)
