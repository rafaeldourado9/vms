"""Casos de uso do bounded context de câmeras e agents."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

from vms.cameras.domain import (
    Agent,
    Camera,
    CameraConfig,
    CameraManufacturer,
    OnvifProbeResult,
    StreamProtocol,
    StreamUrls,
)
from vms.cameras.mediamtx import MediaMTXClient
from vms.cameras.repository import AgentRepositoryPort, CameraRepositoryPort
from vms.core.config import get_settings
from vms.core.exceptions import NotFoundError, ValidationError
from vms.iam.domain import ApiKeyOwnerType
from vms.iam.service import ApiKeyService


class CameraService:
    """Casos de uso de gerenciamento de câmeras."""

    def __init__(
        self,
        camera_repo: CameraRepositoryPort,
        mediamtx: MediaMTXClient | None = None,
    ) -> None:
        self._cameras = camera_repo
        self._mediamtx = mediamtx or MediaMTXClient()

    async def create_camera(
        self,
        tenant_id: str,
        name: str,
        manufacturer: str = "generic",
        location: str | None = None,
        retention_days: int = 7,
        stream_protocol: StreamProtocol = StreamProtocol.RTSP_PULL,
        rtsp_url: str | None = None,
        agent_id: str | None = None,
        onvif_url: str | None = None,
        onvif_username: str | None = None,
        onvif_password: str | None = None,
    ) -> Camera:
        """Cria câmera de acordo com o protocolo e registra no MediaMTX."""
        rtmp_stream_key: str | None = None

        if stream_protocol == StreamProtocol.RTMP_PUSH:
            rtmp_stream_key = Camera.generate_stream_key()
            agent_id = None  # rtmp_push não usa agent

        elif stream_protocol == StreamProtocol.ONVIF:
            if not onvif_url:
                raise ValidationError("onvif_url é obrigatório para protocolo ONVIF")
            # Se rtsp_url não foi fornecida, tenta extrair via probe
            if not rtsp_url:
                from vms.cameras.onvif_client import OnvifClient
                probe = await OnvifClient.probe(onvif_url, onvif_username or "", onvif_password or "")
                if probe.reachable and probe.rtsp_url:
                    rtsp_url = probe.rtsp_url
                    if probe.manufacturer and probe.manufacturer != "unknown":
                        manufacturer = probe.manufacturer.lower()

        camera = Camera(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            manufacturer=CameraManufacturer(manufacturer),
            stream_protocol=stream_protocol,
            rtsp_url=rtsp_url,
            rtmp_stream_key=rtmp_stream_key,
            onvif_url=onvif_url,
            onvif_username=onvif_username,
            onvif_password=onvif_password,
            location=location,
            retention_days=retention_days,
            agent_id=agent_id,
        )
        saved = await self._cameras.create(camera)
        await self._mediamtx.add_path(saved.mediamtx_path)
        if saved.agent_id:
            await _notify_agent(saved.agent_id, "camera_added", {"camera_id": saved.id})
        return saved

    async def get_camera(self, camera_id: str, tenant_id: str) -> Camera:
        """Retorna câmera por ID. Lança NotFoundError se não encontrada."""
        camera = await self._cameras.get_by_id(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)
        return camera

    async def list_cameras(
        self, tenant_id: str, is_online: bool | None = None
    ) -> list[Camera]:
        """Lista câmeras do tenant, opcionalmente filtrando por status online."""
        return await self._cameras.list_by_tenant(tenant_id, is_online=is_online)

    async def update_camera(
        self,
        camera_id: str,
        tenant_id: str,
        name: str | None = None,
        rtsp_url: str | None = None,
        onvif_url: str | None = None,
        onvif_username: str | None = None,
        onvif_password: str | None = None,
        manufacturer: str | None = None,
        location: str | None = None,
        retention_days: int | None = None,
        agent_id: str | None = None,
        ptz_supported: bool | None = None,
        is_active: bool | None = None,
    ) -> Camera:
        """Atualiza campos fornecidos da câmera."""
        camera = await self.get_camera(camera_id, tenant_id)
        if name is not None:
            camera.name = name
        if rtsp_url is not None:
            camera.rtsp_url = rtsp_url
        if onvif_url is not None:
            camera.onvif_url = onvif_url
        if onvif_username is not None:
            camera.onvif_username = onvif_username
        if onvif_password is not None:
            camera.onvif_password = onvif_password
        if manufacturer is not None:
            camera.manufacturer = CameraManufacturer(manufacturer)
        if location is not None:
            camera.location = location
        if retention_days is not None:
            camera.retention_days = retention_days
        if agent_id is not None:
            camera.agent_id = agent_id
        if ptz_supported is not None:
            camera.ptz_supported = ptz_supported
        if is_active is not None:
            camera.is_active = is_active
        updated = await self._cameras.update(camera)
        if updated.agent_id:
            await _notify_agent(updated.agent_id, "config_updated", {"camera_id": updated.id})
        return updated

    async def delete_camera(self, camera_id: str, tenant_id: str) -> None:
        """Remove câmera. Best-effort: não falha se MediaMTX inacessível."""
        camera = await self.get_camera(camera_id, tenant_id)
        agent_id = camera.agent_id
        await self._mediamtx.remove_path(camera.mediamtx_path)
        await self._cameras.delete(camera_id, tenant_id)
        if agent_id:
            await _notify_agent(agent_id, "camera_removed", {"camera_id": camera_id})

    async def get_stream_urls(
        self, camera_id: str, tenant_id: str, viewer_token: str, mediamtx_host: str
    ) -> StreamUrls:
        """Gera URLs de streaming assinadas para um viewer."""
        camera = await self.get_camera(camera_id, tenant_id)
        settings = get_settings()
        path = camera.mediamtx_path

        return StreamUrls(
            hls_url=f"http://{mediamtx_host}:8888/{path}/index.m3u8?token={viewer_token}",
            webrtc_url=f"http://{mediamtx_host}:8889/{path}/whep?token={viewer_token}",
            rtsp_url=(
                f"rtsp://{mediamtx_host}:8554/{path}?token={viewer_token}"
                if camera.stream_protocol != StreamProtocol.RTMP_PUSH
                else None
            ),
            token=viewer_token,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes),
        )

    async def onvif_probe(
        self, onvif_url: str, username: str, password: str
    ) -> OnvifProbeResult:
        """Faz probe ONVIF e retorna capacidades da câmera."""
        from vms.cameras.onvif_client import OnvifClient
        return await OnvifClient.probe(onvif_url, username, password)


class AgentService:
    """Casos de uso de gerenciamento de agents."""

    def __init__(
        self,
        agent_repo: AgentRepositoryPort,
        camera_repo: CameraRepositoryPort,
        api_key_service: ApiKeyService,
    ) -> None:
        self._agents = agent_repo
        self._cameras = camera_repo
        self._api_keys = api_key_service

    async def create_agent(
        self, tenant_id: str, name: str
    ) -> tuple[Agent, str]:
        """
        Cria agent e emite API key.

        Retorna (agent, api_key_plain). A chave deve ser exibida uma única vez.
        """
        agent = Agent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
        )
        saved = await self._agents.create(agent)
        api_key, plain = await self._api_keys.issue_api_key(
            tenant_id=tenant_id,
            owner_type=ApiKeyOwnerType.AGENT,
            owner_id=saved.id,
        )
        return saved, plain

    async def get_agent(self, agent_id: str, tenant_id: str) -> Agent:
        """Retorna agent por ID. Lança NotFoundError se não encontrado."""
        agent = await self._agents.get_by_id(agent_id, tenant_id)
        if not agent:
            raise NotFoundError("Agent", agent_id)
        return agent

    async def list_agents(self, tenant_id: str) -> list[Agent]:
        """Lista todos os agents do tenant."""
        return await self._agents.list_by_tenant(tenant_id)

    async def get_agent_config(
        self, agent_id: str, tenant_id: str
    ) -> tuple[Agent, list[CameraConfig]]:
        """Retorna agent e lista de configurações de câmera para o agent (somente rtsp_pull)."""
        agent = await self.get_agent(agent_id, tenant_id)
        cameras = await self._cameras.list_by_agent(agent_id, tenant_id)
        settings = get_settings()
        configs = [
            CameraConfig(
                id=cam.id,
                name=cam.name,
                rtsp_url=cam.rtsp_url or "",
                rtmp_push_url=(
                    f"{settings.mediamtx_rtmp_url}/{cam.mediamtx_path}"
                ),
                enabled=cam.is_active,
            )
            for cam in cameras
            if cam.stream_protocol in (StreamProtocol.RTSP_PULL, StreamProtocol.ONVIF)
            and cam.rtsp_url
        ]
        return agent, configs

    async def register_heartbeat(
        self,
        agent_id: str,
        tenant_id: str,
        version: str,
        streams_running: int,
        streams_failed: int,
    ) -> Agent:
        """Registra heartbeat do agent e atualiza status para online."""
        agent = await self.get_agent(agent_id, tenant_id)
        agent.mark_online(version, streams_running, streams_failed)
        return await self._agents.update(agent)

    async def delete_agent(self, agent_id: str, tenant_id: str) -> None:
        """Remove agent — a API key associada é revogada via ApiKeyService."""
        agent = await self.get_agent(agent_id, tenant_id)
        agent.mark_offline()
        await self._agents.update(agent)


async def _notify_agent(agent_id: str, event: str, data: dict) -> None:
    """Publica evento no Redis channel do agent (best-effort, não falha)."""
    try:
        from vms.core.config import get_settings
        import redis.asyncio as aioredis

        settings = get_settings()
        client = aioredis.from_url(settings.redis_url)
        payload = json.dumps({"event": event, **data})
        await client.publish(f"agent:{agent_id}:config", payload)
        await client.aclose()
    except Exception as exc:
        logger.warning("Falha ao notificar agent %s: %s", agent_id, exc)
