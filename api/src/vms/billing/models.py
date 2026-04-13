"""Modelos SQLAlchemy para faturamento — Licenciamento."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from vms.infrastructure.database.connection import Base


class LicenseModel(Base):
    """Tabela de licenças por câmera."""

    __tablename__ = "licenses"
    __table_args__ = (
        Index('ix_licenses_tenant', 'tenant_id'),
        Index('ix_licenses_camera', 'camera_id'),
        Index('ix_licenses_type', 'license_type'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    camera_id = Column(UUID(as_uuid=True), nullable=True)  # NULL = licença avulsa
    license_type = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, server_default=text("'active'"))
    storage_limit_gb = Column(Integer(), nullable=True)
    analytics_enabled = Column(Boolean(), nullable=False, server_default=text("false"))
    activated_at = Column(DateTime(timezone=True), server_default=text("now()"))
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
