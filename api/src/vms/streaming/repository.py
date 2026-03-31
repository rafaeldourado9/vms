"""Ports (interfaces) e implementações SQLAlchemy para streaming."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from vms.streaming.domain import StreamSession
from vms.streaming.models import StreamSessionModel


# ─── Ports (interfaces) ───────────────────────────────────────────────────────

class StreamSessionRepositoryPort(Protocol):
    """Interface do repositório de sessões de streaming."""

    async def create(self, session: StreamSession) -> StreamSession: ...

    async def get_active_by_path(
        self, mediamtx_path: str
    ) -> StreamSession | None: ...

    async def end_session(self, mediamtx_path: str) -> StreamSession | None: ...


# ─── Conversores ORM ↔ Domain ─────────────────────────────────────────────────

def _to_domain(m: StreamSessionModel) -> StreamSession:
    """Converte modelo ORM para entidade de domínio StreamSession."""
    return StreamSession(
        id=m.id,
        tenant_id=m.tenant_id,
        camera_id=m.camera_id,
        mediamtx_path=m.mediamtx_path,
        started_at=m.started_at,
        ended_at=m.ended_at,
    )


# ─── Implementação SQLAlchemy ────────────────────────────────────────────────

class StreamSessionRepository:
    """Repositório SQLAlchemy para StreamSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, stream_session: StreamSession) -> StreamSession:
        """Persiste nova sessão de streaming."""
        model = StreamSessionModel(
            id=stream_session.id,
            tenant_id=stream_session.tenant_id,
            camera_id=stream_session.camera_id,
            mediamtx_path=stream_session.mediamtx_path,
            started_at=stream_session.started_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_active_by_path(
        self, mediamtx_path: str
    ) -> StreamSession | None:
        """Busca sessão ativa pelo path do MediaMTX."""
        stmt = select(StreamSessionModel).where(
            StreamSessionModel.mediamtx_path == mediamtx_path,
            StreamSessionModel.ended_at.is_(None),
        )
        result = await self._session.scalar(stmt)
        return _to_domain(result) if result else None

    async def end_session(self, mediamtx_path: str) -> StreamSession | None:
        """Encerra sessão ativa pelo path. Retorna sessão encerrada ou None."""
        stmt = select(StreamSessionModel).where(
            StreamSessionModel.mediamtx_path == mediamtx_path,
            StreamSessionModel.ended_at.is_(None),
        )
        model = await self._session.scalar(stmt)
        if not model:
            return None

        now = datetime.now(UTC)
        model.ended_at = now
        await self._session.flush()
        return _to_domain(model)
