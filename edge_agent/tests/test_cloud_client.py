"""Testes unitários do CloudClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from agent.cloud_client import AgentConfig, CloudClient
from agent.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Settings de teste com dados fictícios."""
    return Settings(
        agent_id="agent-test-123",
        agent_api_key="test-api-key",
        vms_api_url="http://vms-api:8000",  # type: ignore[arg-type]
    )


@pytest.fixture
async def client(settings: Settings) -> CloudClient:
    """CloudClient inicializado para teste."""
    c = CloudClient(settings)
    await c.start()
    return c


class TestGetConfig:
    """Testes de busca de configuração."""

    @respx.mock
    async def test_retorna_cameras_ativas(self, settings: Settings) -> None:
        """get_config retorna lista de câmeras da API."""
        respx.get("http://vms-api:8000/api/v1/agents/me/config").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agent_id": "agent-test-123",
                    "cameras": [
                        {
                            "id": "cam-1",
                            "name": "Câmera Entrada",
                            "rtsp_url": "rtsp://cam1:554/live",
                            "rtmp_push_url": "rtmp://mediamtx:1935/tenant-1/cam-1",
                            "enabled": True,
                        }
                    ]
                },
            )
        )

        c = CloudClient(settings)
        await c.start()
        config = await c.get_config()
        await c.stop()

        assert isinstance(config, AgentConfig)
        assert config.agent_id == "agent-test-123"
        assert len(config.cameras) == 1
        assert config.cameras[0].camera_id == "cam-1"
        assert config.cameras[0].rtsp_url == "rtsp://cam1:554/live"

    @respx.mock
    async def test_config_vazia_quando_sem_cameras(self, settings: Settings) -> None:
        """get_config retorna lista vazia quando API não retorna câmeras."""
        respx.get("http://vms-api:8000/api/v1/agents/me/config").mock(
            return_value=httpx.Response(200, json={"agent_id": "agent-test-123", "cameras": []})
        )

        c = CloudClient(settings)
        await c.start()
        config = await c.get_config()
        await c.stop()

        assert config.cameras == []

    @respx.mock
    async def test_levanta_erro_em_http_error(self, settings: Settings) -> None:
        """get_config propaga HTTPStatusError em resposta 4xx."""
        respx.get("http://vms-api:8000/api/v1/agents/me/config").mock(
            return_value=httpx.Response(401, json={"error": "unauthorized"})
        )

        c = CloudClient(settings)
        await c.start()

        with pytest.raises(httpx.HTTPStatusError):
            await c.get_config()

        await c.stop()

    @respx.mock
    async def test_usa_rtmp_push_url_da_api(self, settings: Settings) -> None:
        """get_config usa rtmp_push_url retornado pela API como mediamtx_path."""
        respx.get("http://vms-api:8000/api/v1/agents/me/config").mock(
            return_value=httpx.Response(
                200,
                json={
                    "agent_id": "agent-test-123",
                    "cameras": [
                        {
                            "id": "cam-xyz",
                            "name": "Câmera XYZ",
                            "rtsp_url": "rtsp://cam:554/live",
                            "rtmp_push_url": "rtmp://mediamtx:1935/tenant-abc/cam-xyz",
                            "enabled": True,
                        }
                    ]
                },
            )
        )

        c = CloudClient(settings)
        await c.start()
        config = await c.get_config()
        await c.stop()

        assert config.cameras[0].mediamtx_path == "rtmp://mediamtx:1935/tenant-abc/cam-xyz"


class TestSendHeartbeat:
    """Testes de envio de heartbeat."""

    @respx.mock
    async def test_envia_heartbeat_online(self, settings: Settings) -> None:
        """send_heartbeat faz POST para /agents/me/heartbeat."""
        route = respx.post("http://vms-api:8000/api/v1/agents/me/heartbeat").mock(
            return_value=httpx.Response(200, json={"status": "online"})
        )

        c = CloudClient(settings)
        await c.start()
        await c.send_heartbeat("online")
        await c.stop()

        assert route.called

    @respx.mock
    async def test_heartbeat_nao_lanca_excecao_em_falha(self, settings: Settings) -> None:
        """send_heartbeat não propaga erro de rede — apenas loga warning."""
        respx.post("http://vms-api:8000/api/v1/agents/me/heartbeat").mock(
            side_effect=httpx.ConnectError("sem rede")
        )

        c = CloudClient(settings)
        await c.start()
        # Não deve lançar
        await c.send_heartbeat("online")
        await c.stop()

    async def test_ensure_client_sem_start_lanca(self, settings: Settings) -> None:
        """Chamar get_config sem start levanta RuntimeError."""
        c = CloudClient(settings)
        with pytest.raises(RuntimeError, match="não iniciado"):
            await c.get_config()

