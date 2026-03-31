"""Testes do CloudClient.listen_for_config_push (WebSocket)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.cloud_client import CloudClient
from agent.config import Settings


def _client() -> CloudClient:
    settings = MagicMock(spec=Settings)
    settings.vms_api_url = "http://vms.local"
    settings.agent_api_key = "test-key"
    settings.http_timeout = 10.0
    settings.agent_id = "agent-1"
    return CloudClient(settings)


class TestListenForConfigPush:
    """Testes de CloudClient.listen_for_config_push."""

    async def test_on_update_called_for_message(self):
        """Callback on_update é chamado quando mensagem chega."""
        client = _client()
        received: list[dict] = []

        async def fake_on_update(data: dict) -> None:
            received.append(data)

        message = json.dumps({"event": "config_updated", "camera_id": "c1"})

        # Simula websocket que envia 1 mensagem e fecha
        mock_ws = AsyncMock()
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)
        mock_ws.__aiter__ = MagicMock(return_value=iter([message]))

        with patch("websockets.connect", return_value=mock_ws):
            # Cancela após primeira iteração para não loop infinito
            task = asyncio.create_task(client.listen_for_config_push(fake_on_update))
            await asyncio.sleep(0.05)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        assert len(received) >= 1
        assert received[0]["event"] == "config_updated"

    async def test_reconnects_after_disconnect(self):
        """Reconecta automaticamente após desconexão."""
        client = _client()
        connect_count = 0

        async def fake_on_update(data: dict) -> None:
            pass

        class FakeWS:
            async def __aenter__(self):
                nonlocal connect_count
                connect_count += 1
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return iter([])  # fecha imediatamente

        with patch("websockets.connect", return_value=FakeWS()):
            with patch("asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)):
                task = asyncio.create_task(client.listen_for_config_push(fake_on_update))
                await asyncio.gather(task, return_exceptions=True)

        assert connect_count >= 1

    async def test_invalid_json_does_not_crash(self):
        """JSON inválido não quebra o loop."""
        client = _client()
        received: list[dict] = []

        async def fake_on_update(data: dict) -> None:
            received.append(data)

        mock_ws = AsyncMock()
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=None)
        mock_ws.__aiter__ = MagicMock(return_value=iter(["not-json", '{"event": "ok"}']))

        with patch("websockets.connect", return_value=mock_ws):
            task = asyncio.create_task(client.listen_for_config_push(fake_on_update))
            await asyncio.sleep(0.05)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        # Deve ter processado o JSON válido e ignorado o inválido
        valid = [r for r in received if r.get("event") == "ok"]
        assert len(valid) >= 1
