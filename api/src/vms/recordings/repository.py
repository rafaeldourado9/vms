"""Ports (interfaces) e implementações SQLAlchemy para gravações e clipes."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.recordings.domain import Clip, ClipStatus, RecordingSegment
from vms.recordings.models import ClipModel, RecordingSegmentModel


# ─── Ports (interfaces) ───────────────────────────────────────────────────────

class RecordingSegmentRepositoryPort(Protocol):
    """Interface do repositório de segmentos de gravação."""

    async def create(self, segment: RecordingSegment) -> RecordingSegment: ...

    async def list_by_camera(
        self,
        tenant_id: str,
        camera_id: str,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RecordingSegment], int]: ...

    async def delete_older_than(
        self, tenant_id: str, camera_id: str, before_date: datetime
    ) -> int: ...


class ClipRepositoryPort(Protocol):
    """Interface do repositório de clipes."""

    async def create(self, clip: Clip) -> Clip: ...
    async def get_by_id(self, clip_id: str, tenant_id: str) -> Clip | None: ...
    async def list_by_tenant(
        self, tenant_id: str, camera_id: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[Clip], int]: ...
    async def update(self, clip: Clip) -> Clip: ...


# ─── Conversores ORM ↔ Domain ─────────────────────────────────────────────────

def _segment_to_domain(m: RecordingSegmentModel) -> RecordingSegment:
    """Converte modelo ORM para entidade de domínio RecordingSegment."""
    return RecordingSegment(
        id=m.id,
        tenant_id=m.tenant_id,
        camera_id=m.camera_id,
        mediamtx_path=m.mediamtx_path,
        file_path=m.file_path,
        started_at=m.started_at,
        ended_at=m.ended_at,
        duration_seconds=m.duration_seconds,
        size_bytes=m.size_bytes,
    )


def _clip_to_domain(m: ClipModel) -> Clip:
    """Converte modelo ORM para entidade de domínio Clip."""
    return Clip(
        id=m.id,
        tenant_id=m.tenant_id,
        camera_id=m.camera_id,
        starts_at=m.starts_at,
        ends_at=m.ends_at,
        status=ClipStatus(m.status),
        file_path=m.file_path,
        vms_event_id=m.vms_event_id,
        created_at=m.created_at,
    )


# ─── Implementações SQLAlchemy ────────────────────────────────────────────────

class RecordingSegmentRepository:
    """Repositório SQLAlchemy para RecordingSegment."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, segment: RecordingSegment) -> RecordingSegment:
        """Persiste novo segmento de gravação."""
        model = RecordingSegmentModel(
            id=segment.id,
            tenant_id=segment.tenant_id,
            camera_id=segment.camera_id,
            mediamtx_path=segment.mediamtx_path,
            file_path=segment.file_path,
            started_at=segment.started_at,
            ended_at=segment.ended_at,
            duration_seconds=segment.duration_seconds,
            size_bytes=segment.size_bytes,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _segment_to_domain(model)

    async def list_by_camera(
        self,
        tenant_id: str,
        camera_id: str,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RecordingSegment], int]:
        """Lista segmentos por câmera com filtro de período. Retorna (items, total)."""
        base = select(RecordingSegmentModel).where(
            RecordingSegmentModel.tenant_id == tenant_id,
            RecordingSegmentModel.camera_id == camera_id,
        )
        if started_after:
            base = base.where(RecordingSegmentModel.started_at >= started_after)
        if started_before:
            base = base.where(RecordingSegmentModel.started_at <= started_before)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = await self._session.scalar(count_stmt) or 0

        stmt = base.order_by(RecordingSegmentModel.started_at.desc()).limit(limit).offset(offset)
        result = await self._session.scalars(stmt)
        return [_segment_to_domain(m) for m in result.all()], total

    async def delete_older_than(
        self, tenant_id: str, camera_id: str, before_date: datetime
    ) -> int:
        """Remove segmentos anteriores a before_date. Retorna quantidade removida."""
        stmt = delete(RecordingSegmentModel).where(
            RecordingSegmentModel.tenant_id == tenant_id,
            RecordingSegmentModel.camera_id == camera_id,
            RecordingSegmentModel.started_at < before_date,
        )
        result = await self._session.execute(stmt)
        return result.rowcount


class ClipRepository:
    """Repositório SQLAlchemy para Clip."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, clip: Clip) -> Clip:
        """Persiste novo clipe."""
        model = ClipModel(
            id=clip.id,
            tenant_id=clip.tenant_id,
            camera_id=clip.camera_id,
            starts_at=clip.starts_at,
            ends_at=clip.ends_at,
            status=clip.status.value,
            vms_event_id=clip.vms_event_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _clip_to_domain(model)

    async def get_by_id(self, clip_id: str, tenant_id: str) -> Clip | None:
        """Busca clipe por ID dentro do tenant."""
        stmt = select(ClipModel).where(
            ClipModel.id == clip_id,
            ClipModel.tenant_id == tenant_id,
        )
        result = await self._session.scalar(stmt)
        return _clip_to_domain(result) if result else None

    async def list_by_tenant(
        self,
        tenant_id: str,
        camera_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Clip], int]:
        """Lista clipes do tenant. Retorna (items, total)."""
        base = select(ClipModel).where(ClipModel.tenant_id == tenant_id)
        if camera_id:
            base = base.where(ClipModel.camera_id == camera_id)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = await self._session.scalar(count_stmt) or 0

        stmt = base.order_by(ClipModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.scalars(stmt)
        return [_clip_to_domain(m) for m in result.all()], total

    async def update(self, clip: Clip) -> Clip:
        """Atualiza clipe existente."""
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(ClipModel)
            .where(ClipModel.id == clip.id, ClipModel.tenant_id == clip.tenant_id)
            .values(status=clip.status.value, file_path=clip.file_path)
        )
        await self._session.execute(stmt)
        return clip
