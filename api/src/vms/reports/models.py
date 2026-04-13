"""Modelos SQLAlchemy para relatórios."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from vms.infrastructure.database.connection import Base


class ReportModel(Base):
    """Tabela de relatórios gerados."""

    __tablename__ = "reports"
    __table_args__ = (
        Index('ix_reports_tenant_created', 'tenant_id', 'created_at'),
        Index('ix_reports_status', 'status'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    report_type = Column(String(50), nullable=False)
    parameters = Column(JSONB, nullable=False, server_default=text("'{}'"))
    status = Column(String(20), nullable=False, server_default=text("'pending'"))
    file_path = Column(String(1000), nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} status={self.status}>"
