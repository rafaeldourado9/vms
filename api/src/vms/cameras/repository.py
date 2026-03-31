"""Ports (interfaces) e implementações SQLAlchemy para câmeras e agents."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vms.cameras.domain import Agent, AgentStatus, Camera, CameraManufacturer, StreamProtocol
from vms.cameras.models import AgentModel, CameraModel


# ─── Ports (interfaces) ───────────────────────────────────────────────────────

class CameraRepositoryPort(Protocol):
    """Interface do repositório de câmeras."""

    async def get_by_id(self, camera_id: str, tenant_id: str) -> Camera | None: ...
    async def list_by_tenant(
        self, tenant_id: str, is_online: bool | None = None
    ) -> list[Camera]: ...
    async def list_by_agent(self, agent_id: str, tenant_id: str) -> list[Camera]: ...
    async def create(self, camera: Camera) -> Camera: ...
    async def update(self, camera: Camera) -> Camera: ...
    async def delete(self, camera_id: str, tenant_id: str) -> bool: ...


class AgentRepositoryPort(Protocol):
    """Interface do repositório de agents."""

    async def get_by_id(self, agent_id: str, tenant_id: str) -> Agent | None: ...
    async def list_by_tenant(self, tenant_id: str) -> list[Agent]: ...
    async def create(self, agent: Agent) -> Agent: ...
    async def update(self, agent: Agent) -> Agent: ...


# ─── Conversores ORM ↔ Domain ─────────────────────────────────────────────────

def _camera_to_domain(m: CameraModel) -> Camera:
    """Converte modelo ORM para entidade de domínio Camera."""
    return Camera(
        id=m.id,
        tenant_id=m.tenant_id,
        name=m.name,
        stream_protocol=StreamProtocol(m.stream_protocol),
        rtsp_url=m.rtsp_url,
        rtmp_stream_key=m.rtmp_stream_key,
        onvif_url=m.onvif_url,
        onvif_username=m.onvif_username,
        onvif_password=m.onvif_password,
        manufacturer=CameraManufacturer(m.manufacturer),
        location=m.location,
        agent_id=m.agent_id,
        retention_days=m.retention_days,
        is_active=m.is_active,
        is_online=m.is_online,
        last_seen_at=m.last_seen_at,
        created_at=m.created_at,
    )


def _agent_to_domain(m: AgentModel) -> Agent:
    """Converte modelo ORM para entidade de domínio Agent."""
    return Agent(
        id=m.id,
        tenant_id=m.tenant_id,
        name=m.name,
        status=AgentStatus(m.status),
        last_heartbeat_at=m.last_heartbeat_at,
        version=m.version,
        streams_running=m.streams_running,
        streams_failed=m.streams_failed,
        created_at=m.created_at,
    )


# ─── Implementações SQLAlchemy ────────────────────────────────────────────────

class CameraRepository:
    """Repositório SQLAlchemy para Camera."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, camera_id: str, tenant_id: str) -> Camera | None:
        """Busca câmera por ID dentro do tenant."""
        stmt = select(CameraModel).where(
            CameraModel.id == camera_id,
            CameraModel.tenant_id == tenant_id,
        )
        result = await self._session.scalar(stmt)
        return _camera_to_domain(result) if result else None

    async def list_by_tenant(
        self, tenant_id: str, is_online: bool | None = None
    ) -> list[Camera]:
        """Lista câmeras do tenant, opcionalmente filtrando por status online."""
        stmt = select(CameraModel).where(
            CameraModel.tenant_id == tenant_id,
            CameraModel.is_active.is_(True),
        )
        if is_online is not None:
            stmt = stmt.where(CameraModel.is_online.is_(is_online))
        result = await self._session.scalars(stmt)
        return [_camera_to_domain(m) for m in result.all()]

    async def list_by_agent(self, agent_id: str, tenant_id: str) -> list[Camera]:
        """Lista câmeras vinculadas a um agent."""
        stmt = select(CameraModel).where(
            CameraModel.agent_id == agent_id,
            CameraModel.tenant_id == tenant_id,
            CameraModel.is_active.is_(True),
        )
        result = await self._session.scalars(stmt)
        return [_camera_to_domain(m) for m in result.all()]

    async def create(self, camera: Camera) -> Camera:
        """Persiste nova câmera."""
        model = CameraModel(
            id=camera.id,
            tenant_id=camera.tenant_id,
            name=camera.name,
            stream_protocol=camera.stream_protocol.value,
            rtsp_url=camera.rtsp_url,
            rtmp_stream_key=camera.rtmp_stream_key,
            onvif_url=camera.onvif_url,
            onvif_username=camera.onvif_username,
            onvif_password=camera.onvif_password,
            manufacturer=camera.manufacturer.value,
            location=camera.location,
            agent_id=camera.agent_id,
            retention_days=camera.retention_days,
            is_active=camera.is_active,
            is_online=camera.is_online,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _camera_to_domain(model)

    async def update(self, camera: Camera) -> Camera:
        """Atualiza câmera existente."""
        stmt = (
            update(CameraModel)
            .where(
                CameraModel.id == camera.id,
                CameraModel.tenant_id == camera.tenant_id,
            )
            .values(
                name=camera.name,
                rtsp_url=camera.rtsp_url,
                rtmp_stream_key=camera.rtmp_stream_key,
                onvif_url=camera.onvif_url,
                onvif_username=camera.onvif_username,
                onvif_password=camera.onvif_password,
                manufacturer=camera.manufacturer.value,
                location=camera.location,
                agent_id=camera.agent_id,
                retention_days=camera.retention_days,
                is_active=camera.is_active,
                is_online=camera.is_online,
                last_seen_at=camera.last_seen_at,
            )
        )
        await self._session.execute(stmt)
        return camera

    async def delete(self, camera_id: str, tenant_id: str) -> bool:
        """Remove câmera (soft delete via is_active=False). Retorna False se não encontrada."""
        stmt = (
            update(CameraModel)
            .where(
                CameraModel.id == camera_id,
                CameraModel.tenant_id == tenant_id,
            )
            .values(is_active=False)
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0


class AgentRepository:
    """Repositório SQLAlchemy para Agent."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, agent_id: str, tenant_id: str) -> Agent | None:
        """Busca agent por ID dentro do tenant."""
        stmt = select(AgentModel).where(
            AgentModel.id == agent_id,
            AgentModel.tenant_id == tenant_id,
        )
        result = await self._session.scalar(stmt)
        return _agent_to_domain(result) if result else None

    async def list_by_tenant(self, tenant_id: str) -> list[Agent]:
        """Lista todos os agents de um tenant."""
        stmt = select(AgentModel).where(AgentModel.tenant_id == tenant_id)
        result = await self._session.scalars(stmt)
        return [_agent_to_domain(m) for m in result.all()]

    async def create(self, agent: Agent) -> Agent:
        """Persiste novo agent."""
        model = AgentModel(
            id=agent.id,
            tenant_id=agent.tenant_id,
            name=agent.name,
            status=agent.status.value,
            streams_running=agent.streams_running,
            streams_failed=agent.streams_failed,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _agent_to_domain(model)

    async def update(self, agent: Agent) -> Agent:
        """Atualiza agent existente."""
        stmt = (
            update(AgentModel)
            .where(AgentModel.id == agent.id, AgentModel.tenant_id == agent.tenant_id)
            .values(
                status=agent.status.value,
                last_heartbeat_at=agent.last_heartbeat_at,
                version=agent.version,
                streams_running=agent.streams_running,
                streams_failed=agent.streams_failed,
            )
        )
        await self._session.execute(stmt)
        return agent
