"""Casos de uso do bounded context de câmeras e agents."""
from __future__ import annotations

import uuid

from vms.cameras.domain import Agent, Camera, CameraConfig, CameraManufacturer
from vms.cameras.mediamtx import MediaMTXClient
from vms.cameras.repository import AgentRepositoryPort, CameraRepositoryPort
from vms.core.config import get_settings
from vms.core.exceptions import NotFoundError
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
        rtsp_url: str,
        manufacturer: str = "generic",
        location: str | None = None,
        retention_days: int = 7,
        agent_id: str | None = None,
    ) -> Camera:
        """Cria câmera, registra path no MediaMTX e persiste no banco."""
        camera = Camera(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name,
            rtsp_url=rtsp_url,
            manufacturer=CameraManufacturer(manufacturer),
            location=location,
            retention_days=retention_days,
            agent_id=agent_id,
        )
        saved = await self._cameras.create(camera)
        await self._mediamtx.add_path(saved.mediamtx_path)
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
        manufacturer: str | None = None,
        location: str | None = None,
        retention_days: int | None = None,
        agent_id: str | None = None,
        is_active: bool | None = None,
    ) -> Camera:
        """Atualiza campos fornecidos da câmera."""
        camera = await self.get_camera(camera_id, tenant_id)
        if name is not None:
            camera.name = name
        if rtsp_url is not None:
            camera.rtsp_url = rtsp_url
        if manufacturer is not None:
            camera.manufacturer = CameraManufacturer(manufacturer)
        if location is not None:
            camera.location = location
        if retention_days is not None:
            camera.retention_days = retention_days
        if agent_id is not None:
            camera.agent_id = agent_id
        if is_active is not None:
            camera.is_active = is_active
        return await self._cameras.update(camera)

    async def delete_camera(self, camera_id: str, tenant_id: str) -> None:
        """Remove câmera. Best-effort: não falha se MediaMTX inacessível."""
        camera = await self.get_camera(camera_id, tenant_id)
        await self._mediamtx.remove_path(camera.mediamtx_path)
        await self._cameras.delete(camera_id, tenant_id)


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
        """Retorna agent e lista de configurações de câmera para o agent."""
        agent = await self.get_agent(agent_id, tenant_id)
        cameras = await self._cameras.list_by_agent(agent_id, tenant_id)
        settings = get_settings()
        configs = [
            CameraConfig(
                id=cam.id,
                name=cam.name,
                rtsp_url=cam.rtsp_url,
                rtmp_push_url=(
                    f"{settings.mediamtx_rtmp_url}/{cam.mediamtx_path}"
                ),
                enabled=cam.is_active,
            )
            for cam in cameras
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
