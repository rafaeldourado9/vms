"""Modelos SQLAlchemy ORM para o bounded context de streaming."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from vms.core.database import Base


def _uuid() -> str:
    """Gera UUID v4 como string."""
    return str(uuid.uuid4())


class StreamSessionModel(Base):
    """Tabela de sessões de streaming ativas e encerradas."""

    __tablename__ = "stream_sessions"
    __table_args__ = (
        Index("ix_stream_sessions_tenant_camera", "tenant_id", "camera_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mediamtx_path: Mapped[str] = mapped_column(String(500), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
