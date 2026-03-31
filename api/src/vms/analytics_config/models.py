"""Modelos SQLAlchemy ORM para o bounded context de configuração de analytics."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy import JSON as JSONB  # Compatível com SQLite para testes
from sqlalchemy.orm import Mapped, mapped_column

from vms.core.database import Base


def _uuid() -> str:
    """Gera UUID v4 como string."""
    return str(uuid.uuid4())


class RegionOfInterestModel(Base):
    """Tabela de regiões de interesse para análise de IA."""

    __tablename__ = "regions_of_interest"
    __table_args__ = (
        Index("ix_roi_tenant_camera", "tenant_id", "camera_id"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ia_type: Mapped[str] = mapped_column(String(100), nullable=False)
    polygon_points: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
