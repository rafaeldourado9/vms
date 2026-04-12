"""Modelos de Analytics — ROIs, plugins instalados e eventos."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vms.core.database import Base


class AnalyticsROI(Base):
    """Região de interesse (zona de detecção) para um plugin em uma câmera."""

    __tablename__ = "analytics_rois"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Polígono normalizado: [[x, y], ...] onde x, y ∈ [0, 1]
    polygon: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class PluginInstallation(Base):
    """Plugin instalado em um edge agent."""

    __tablename__ = "plugin_installations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    plugin_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")
    edge_agent_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="installed", index=True)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fps_target: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    events: Mapped[list[AnalyticsEvent]] = relationship(back_populates="plugin_installation", lazy="select")


class AnalyticsEvent(Base):
    """Evento gerado por plugin de analytics."""

    __tablename__ = "analytics_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable: eventos do analytics service não precisam de instalação registrada
    plugin_installation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plugin_installations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    camera_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    camera_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plugin_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info", index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    snapshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    plugin_installation: Mapped[PluginInstallation | None] = relationship(
        back_populates="events", lazy="select"
    )
