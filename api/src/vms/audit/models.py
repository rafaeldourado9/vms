"""Modelos SQLAlchemy para auditoria."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from vms.infrastructure.database.connection import Base


class AuditLogModel(Base):
    """
    Modelo para logs de auditoria.

    Tabela particionada por RANGE(occurred_at) — partições mensais.
    Regra: NUNCA UPDATE ou DELETE nesta tabela.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index('ix_audit_log_tenant_occurred', 'tenant_id', 'occurred_at'),
        Index('ix_audit_log_user_occurred', 'user_id', 'occurred_at'),
        Index('ix_audit_log_action_occurred', 'action', 'occurred_at'),
        Index('ix_audit_log_resource', 'resource_type', 'resource_id'),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(UUID(as_uuid=False), nullable=False)
    user_id = Column(UUID(as_uuid=False), nullable=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(UUID(as_uuid=False), nullable=True)
    resource_name = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max = 45 chars
    user_agent = Column(Text(), nullable=True)
    request_id = Column(UUID(as_uuid=False), nullable=True)
    payload = Column(JSONB(), nullable=True, server_default=text("'{}'"))
    result = Column(String(20), nullable=True, server_default=text("'success'"))
    occurred_at = Column(DateTime(timezone=True), nullable=True, server_default=text("now()"))

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action} resource={self.resource_type}:{self.resource_id}>"
