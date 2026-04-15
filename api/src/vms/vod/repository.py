"""Repositório SQLAlchemy para VOD."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.vod.domain import VODStream
from vms.vod.models import VODStreamModel


class VODRepositoryPort(Protocol):
    """Interface do repositório VOD."""

    async def create(self, stream: VODStream) -> VODStream: ...
    async def get_by_id(self, stream_id: str, tenant_id: str) -> VODStream | None: ...
    async def update(self, stream: VODStream) -> VODStream: ...
    async def cleanup_expired(self, tenant_id: str, before_date: datetime) -> int: ...


def _vod_to_domain(model: VODStreamModel) -> VODStream:
    """Converte modelo ORM para entidade de domínio VODStream."""
    return VODStream(
        id=model.id,
        tenant_id=model.tenant_id,
        camera_id=model.camera_id,
        segments=model.segments or [],
        started_at=model.started_at,
        ended_at=model.ended_at,
        playlist_path=model.playlist_path or "",
        status=model.status or "pending",
        error=model.error,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class VODRepository:
    """Repositório SQLAlchemy para VODStream."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, stream: VODStream) -> VODStream:
        """Cria novo stream VOD."""
        model = VODStreamModel(
            id=stream.id,
            tenant_id=stream.tenant_id,
            camera_id=stream.camera_id,
            segments=stream.segments,
            started_at=stream.started_at,
            ended_at=stream.ended_at,
            playlist_path=stream.playlist_path,
            status=stream.status,
            error=stream.error,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _vod_to_domain(model)

    async def get_by_id(self, stream_id: str, tenant_id: str) -> VODStream | None:
        """Busca stream VOD por ID e tenant."""
        stmt = select(VODStreamModel).where(
            VODStreamModel.id == stream_id,
            VODStreamModel.tenant_id == tenant_id,
        )
        model = await self._session.scalar(stmt)
        return _vod_to_domain(model) if model else None

    async def update(self, stream: VODStream) -> VODStream:
        """Atualiza stream VOD existente."""
        from sqlalchemy import update as sa_update
        from datetime import datetime as dt

        stmt = (
            sa_update(VODStreamModel)
            .where(VODStreamModel.id == stream.id, VODStreamModel.tenant_id == stream.tenant_id)
            .values(
                playlist_path=stream.playlist_path,
                status=stream.status,
                error=stream.error,
                updated_at=dt.utcnow(),
            )
        )
        await self._session.execute(stmt)
        return stream

    async def cleanup_expired(self, tenant_id: str, before_date: datetime) -> int:
        """Remove streams VOD criados antes de before_date."""
        stmt = delete(VODStreamModel).where(
            VODStreamModel.tenant_id == tenant_id,
            VODStreamModel.created_at < before_date,
        )
        result = await self._session.execute(stmt)
        return result.rowcount
