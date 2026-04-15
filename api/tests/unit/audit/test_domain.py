"""Testes de domínio para auditoria."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from vms.audit.domain import AuditLog, AuditLogCreated
from vms.shared.kernel import AuditId, EntityId, TenantId


class TestAuditLog:
    """Testes da entidade AuditLog."""

    def test_create_with_defaults(self):
        """AuditLog criado com valores default."""
        log = AuditLog(
            tenant_id=TenantId("t1"),
            action="camera.created",
        )
        assert log.action == "camera.created"
        assert log.result == "success"
        assert log.payload == {}
        assert log.occurred_at.tzinfo is not None

    def test_is_success_property(self):
        """is_success retorna True para result='success'."""
        log = AuditLog(tenant_id=TenantId("t1"), action="test", result="success")
        assert log.is_success is True

    def test_is_error_for_error_result(self):
        """is_error retorna True para result='error'."""
        log = AuditLog(tenant_id=TenantId("t1"), action="test", result="error")
        assert log.is_error is True

    def test_is_error_for_denied_result(self):
        """is_error retorna True para result='denied'."""
        log = AuditLog(tenant_id=TenantId("t1"), action="test", result="denied")
        assert log.is_error is True

    def test_is_false_for_success(self):
        """is_error retorna False para result='success'."""
        log = AuditLog(tenant_id=TenantId("t1"), action="test", result="success")
        assert log.is_error is False

    def test_record_event_emits_audit_log_created(self):
        """record_event emite AuditLogCreated."""
        log = AuditLog(
            id=AuditId(uuid.uuid4()),
            tenant_id=TenantId("t1"),
            action="camera.created",
            resource_type="camera",
        )
        log.record_event(AuditLogCreated(
            audit_id=log.id,
            tenant_id=log.tenant_id,
            action=log.action,
            resource_type=log.resource_type or "",
        ))
        events = log.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], AuditLogCreated)
        assert events[0].action == "camera.created"
        assert events[0].resource_type == "camera"

    def test_full_audit_log_creation(self):
        """AuditLog completo com todos os campos."""
        log_id = AuditId(uuid.uuid4())
        tenant_id = TenantId(uuid.uuid4())
        user_id = EntityId(uuid.uuid4())
        resource_id = EntityId(uuid.uuid4())
        request_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        log = AuditLog(
            id=log_id,
            tenant_id=tenant_id,
            user_id=user_id,
            user_email="admin@test.com",
            user_role="admin",
            action="recording.downloaded",
            resource_type="recording",
            resource_id=resource_id,
            resource_name="Gravação 2026-04-12",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id=request_id,
            payload={"file_size": 1024, "duration": 300},
            result="success",
            occurred_at=now,
        )

        assert log.id == log_id
        assert log.tenant_id == tenant_id
        assert log.user_id == user_id
        assert log.user_email == "admin@test.com"
        assert log.user_role == "admin"
        assert log.action == "recording.downloaded"
        assert log.resource_type == "recording"
        assert log.resource_id == resource_id
        assert log.resource_name == "Gravação 2026-04-12"
        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "Mozilla/5.0"
        assert log.request_id == request_id
        assert log.payload == {"file_size": 1024, "duration": 300}
        assert log.result == "success"
        assert log.occurred_at == now

    def test_occurred_at_defaults_to_utc(self):
        """occurred_at usa UTC por default."""
        log = AuditLog(tenant_id=TenantId("t1"), action="test")
        assert log.occurred_at.tzinfo is not None
        # Deve estar próximo de agora (margem de 5s)
        diff = abs((datetime.now(timezone.utc) - log.occurred_at).total_seconds())
        assert diff < 5


class TestAuditLogCreated:
    """Testes do domain event AuditLogCreated."""

    def test_event_serialization(self):
        """AuditLogCreated pode ser convertido para dict."""
        event = AuditLogCreated(
            audit_id=AuditId(uuid.uuid4()),
            tenant_id=TenantId("t1"),
            action="camera.created",
            resource_type="camera",
        )
        d = event.to_dict()
        assert d["event_type"] == "AuditLogCreated"
        assert d["action"] == "camera.created"
        assert d["resource_type"] == "camera"

    def test_event_defaults(self):
        """AuditLogCreated com defaults."""
        event = AuditLogCreated()
        assert event.action == ""
        assert event.resource_type == ""
        assert event.audit_id is None
        assert event.tenant_id is None
