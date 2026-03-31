"""Modelos SQLAlchemy ORM para o bounded context de câmeras e agents."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vms.core.database import Base


def _uuid() -> str:
    """Gera UUID v4 como string."""
    return str(uuid.uuid4())


class AgentModel(Base):
    """Tabela de agents locais."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    streams_running: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    streams_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cameras: Mapped[list["CameraModel"]] = relationship(
        "CameraModel", back_populates="agent"
    )


class CameraModel(Base):
    """Tabela de câmeras de segurança."""

    __tablename__ = "cameras"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stream_protocol: Mapped[str] = mapped_column(
        String(50), nullable=False, default="rtsp_pull"
    )
    rtsp_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    rtmp_stream_key: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    onvif_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    onvif_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onvif_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    agent: Mapped[AgentModel | None] = relationship("AgentModel", back_populates="cameras")
