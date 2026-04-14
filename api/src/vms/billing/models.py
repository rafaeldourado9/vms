"""Modelos SQLAlchemy — dois modos: Managed (R$15k/ano) e Self-Hosted (R$20k/ano)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from vms.infrastructure.database.connection import Base


class LicenseKeyModel(Base):
    """Licença de ativação anual — dois modos.

    White Label (Managed):   R$ 15.000/ano + storage R$50/cam/mês + analytics mensal
    White Label (Self-Hosted): R$ 20.000/ano + storage por conta do cliente
    """

    __tablename__ = "license_keys"
    __table_args__ = (
        Index('ix_license_keys_key', 'license_key', unique=True),
        Index('ix_license_keys_tenant', 'tenant_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_key = Column(String(29), nullable=False, unique=True)   # XXXX-XXXXX-XXXXX-XXXXX-XXXXX
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    deployment_model = Column(String(20), nullable=False, server_default=text("'managed'"))  # managed | self_hosted
    status = Column(String(20), nullable=False, server_default=text("'active'"))
    max_cameras = Column(Integer(), nullable=False, server_default=text("0"))
    price_annual = Column(Numeric(10, 2), nullable=False, server_default=text("0"))
    hardware_id = Column(String(64), nullable=True)          # fingerprint (self-hosted)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class AnalyticsPricingModel(Base):
    """Preços de analytics por plugin — renovado mensal.

    Analytics leves (câmeras burras): a partir de R$ 6,90/dia
    Analytics Pro: a partir de R$ 9,90/dia
    """

    __tablename__ = "analytics_pricing"
    __table_args__ = (
        Index('ix_analytics_pricing_plugin', 'plugin_name', unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_name = Column(String(50), nullable=False, unique=True)  # intrusion, people_count, etc.
    tier = Column(String(20), nullable=False, server_default=text("'light'"))  # light | pro
    price_per_camera_per_day = Column(Numeric(10, 4), nullable=False, server_default=text("6.90"))
    description = Column(Text(), nullable=True)
    is_active = Column(Boolean(), nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
