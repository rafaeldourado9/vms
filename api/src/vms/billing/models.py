"""Modelos SQLAlchemy para billing — licença anual + storage + analytics pay-per-use."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from vms.infrastructure.database.connection import Base


class LicenseKeyModel(Base):
    """Licença de ativação anual (pagamento único).

    O cliente compra uma licença com validade de 1 ano.
    Ao ativar, o sistema libera o uso. Renovar = gerar nova key.
    """

    __tablename__ = "license_keys"
    __table_args__ = (
        Index('ix_license_keys_key', 'license_key', unique=True),
        Index('ix_license_keys_tenant', 'tenant_id'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_key = Column(String(24), nullable=False, unique=True)   # VMS-XXXX-XXXX-XXXX-XXXX
    tenant_id = Column(UUID(as_uuid=True), nullable=True)           # NULL = ainda não ativada
    status = Column(String(20), nullable=False, server_default=text("'active'"))
    max_cameras = Column(Integer(), nullable=False, server_default=text("0"))      # 0 = ilimitado
    price_annual = Column(Numeric(10, 2), nullable=False, server_default=text("0"))  # preço pago
    activated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)       # 1 ano após ativação
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class UsageRecordModel(Base):
    """Registro de uso mensal — storage e analytics por câmera.

    Gera fatura automática no início de cada mês.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        Index('ix_usage_records_tenant_period', 'tenant_id', 'period_start'),
        Index('ix_usage_records_type', 'usage_type'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    usage_type = Column(String(30), nullable=False)    # "storage" ou analytics plugin id
    camera_id = Column(UUID(as_uuid=True), nullable=True)  # NULL para storage (global)
    quantity = Column(Numeric(15, 4), nullable=False)   # GB ou número de câmeras
    unit_price = Column(Numeric(10, 4), nullable=False, server_default=text("0"))  # preço por unidade
    total_price = Column(Numeric(15, 4), nullable=False, server_default=text("0"))  # quantity * unit_price
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=text("now()"))


class PricingRuleModel(Base):
    """Tabela de preços — storage mensal e analytics por câmera.

    Editável pelo admin global.
    """

    __tablename__ = "pricing_rules"
    __table_args__ = (
        Index('ix_pricing_rules_type', 'usage_type', unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usage_type = Column(String(30), nullable=False, unique=True)   # "storage", "intrusion", "ppe_detection", etc.
    unit = Column(String(20), nullable=False, server_default=text("'GB'"))  # "GB", "camera/mês"
    price_per_unit = Column(Numeric(10, 4), nullable=False, server_default=text("0"))
    description = Column(Text(), nullable=True)
    is_active = Column(Boolean(), nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
