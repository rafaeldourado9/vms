"""Modelos SQLAlchemy para faturamento."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from vms.infrastructure.database.connection import Base


class BillingPlanModel(Base):
    """Tabela de planos de assinatura."""

    __tablename__ = "billing_plans"
    __table_args__ = (
        Index('ix_billing_plans_slug', 'slug'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(50), nullable=False, unique=True)
    description = Column(Text(), nullable=True)
    price_monthly = Column(Numeric(10, 2), nullable=False, server_default=text("0"))
    max_cameras = Column(Integer(), nullable=True)
    storage_limit_gb = Column(Integer(), nullable=True)
    max_events_per_month = Column(Integer(), nullable=True)
    max_retention_days = Column(Integer(), nullable=False, server_default=text("7"))
    analytics_enabled = Column(Boolean(), nullable=False, server_default=text("true"))
    features = Column(JSONB(), nullable=True, server_default=text("'{}'"))
    is_active = Column(Boolean(), nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class UsageRecordModel(Base):
    """Tabela de registros de consumo."""

    __tablename__ = "usage_records"
    __table_args__ = (
        Index('ix_usage_records_tenant_metric', 'tenant_id', 'metric_name'),
        Index('ix_usage_records_period', 'period_start', 'period_end'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    metric_name = Column(String(50), nullable=False)
    value = Column(Numeric(15, 4), nullable=False)
    unit = Column(String(20), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    recorded_at = Column(DateTime(timezone=True), server_default=text("now()"))
