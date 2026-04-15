"""Testes unitários do AuditService com repo mockado."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from vms.audit.domain import AuditLog, AuditLogCreated
from vms.audit.repository import AuditRepositoryPort
from vms.audit.service import AuditService
from vms.shared.kernel import AuditId, EntityId, TenantId


class TestAuditService:
    """Testes do AuditService."""

    @pytest.fixture
    def repo(self):
        """Repository mockado."""
        repo = AsyncMock(spec=AuditRepositoryPort)

        async def fake_create(log: AuditLog) -> AuditLog:
            return log

        repo.create = AsyncMock(side_effect=fake_create)
        return repo

    @pytest.fixture
    def svc(self, repo):
        return AuditService(repo)

    async def test_log_creates_and_persists(self, svc, repo):
        """log() cria e persiste AuditLog."""
        result = await svc.log(
            tenant_id="t1",
            action="camera.created",
        )
        assert result.action == "camera.created"
        assert result.result == "success"
        repo.create.assert_called_once()

    async def test_log_publishes_domain_event(self, svc):
        """log() publica evento de domínio AuditLogCreated."""
        result = await svc.log(
            tenant_id="t1",
            action="camera.created",
        )
        events = result.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], AuditLogCreated)
        assert events[0].action == "camera.created"

    async def test_log_with_none_user_id(self, svc):
        """log() com user_id=None (ação de sistema)."""
        result = await svc.log(
            tenant_id="t1",
            action="system.startup",
            user_id=None,
        )
        assert result.user_id is None
        assert result.action == "system.startup"

    async def test_log_with_tenant_id_as_string(self, svc):
        """log() aceita tenant_id como string."""
        tenant_str = str(uuid.uuid4())
        result = await svc.log(
            tenant_id=tenant_str,
            action="test.action",
        )
        assert str(result.tenant_id) == tenant_str

    async def test_log_with_tenant_id_object(self, svc):
        """log() aceita tenant_id como TenantId."""
        tenant_id = TenantId(uuid.uuid4())
        result = await svc.log(
            tenant_id=tenant_id,
            action="test.action",
        )
        assert result.tenant_id == tenant_id

    async def test_log_sanitizes_payload(self, svc):
        """log() sanitiza payload automaticamente."""
        result = await svc.log(
            tenant_id="t1",
            action="user.created",
            payload={
                "email": "user@test.com",
                "password": "secret123",
                "token": "abc-xyz",
                "api_key": "vms_123",
            },
        )
        assert result.payload["email"] == "user@test.com"
        assert result.payload["password"] == "[REDACTED]"
        assert result.payload["token"] == "[REDACTED]"
        assert result.payload["api_key"] == "[REDACTED]"

    async def test_log_with_custom_occurred_at(self, svc):
        """log() aceita occurred_at custom."""
        custom_time = datetime(2026, 4, 12, 19, 5, 0, tzinfo=timezone.utc)
        result = await svc.log(
            tenant_id="t1",
            action="test.action",
            occurred_at=custom_time,
        )
        assert result.occurred_at == custom_time

    async def test_log_with_result_error(self, svc):
        """log() com result=error."""
        result = await svc.log(
            tenant_id="t1",
            action="camera.deleted",
            result="error",
        )
        assert result.result == "error"
        assert result.is_error is True

    async def test_log_with_result_denied(self, svc):
        """log() com result=denied."""
        result = await svc.log(
            tenant_id="t1",
            action="camera.deleted",
            result="denied",
        )
        assert result.result == "denied"
        assert result.is_error is True

    async def test_log_with_all_fields(self, svc, repo):
        """log() com todos os campos preenchidos."""
        tenant_id = TenantId(uuid.uuid4())
        user_id = EntityId(uuid.uuid4())
        resource_id = EntityId(uuid.uuid4())
        request_id = uuid.uuid4()

        result = await svc.log(
            tenant_id=tenant_id,
            action="recording.downloaded",
            user_id=user_id,
            user_email="admin@test.com",
            user_role="admin",
            resource_type="recording",
            resource_id=resource_id,
            resource_name="Gravação 2026-04-12",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id=request_id,
            payload={"file_size": 1024},
            result="success",
        )

        assert result.tenant_id == tenant_id
        assert result.user_id == user_id
        assert result.user_email == "admin@test.com"
        assert result.user_role == "admin"
        assert result.resource_type == "recording"
        assert result.resource_id == resource_id
        assert result.resource_name == "Gravação 2026-04-12"
        assert result.ip_address == "192.168.1.100"
        assert result.user_agent == "Mozilla/5.0"
        assert result.request_id == request_id
        assert result.payload == {"file_size": 1024}

    async def test_log_defaults_occurred_at_to_now(self, svc):
        """log() sem occurred_at usa datetime.now(timezone.utc)."""
        before = datetime.now(timezone.utc)
        result = await svc.log(tenant_id="t1", action="test")
        after = datetime.now(timezone.utc)
        assert before <= result.occurred_at <= after


class TestAuditServiceSanitization:
    """Testes de sanitização de payload."""

    def test_sanitize_rem_sensitive_fields(self):
        """Sanitização remove campos sensíveis."""
        payload = {
            "email": "user@test.com",
            "password": "secret",
            "token": "abc",
            "secret": "my-secret",
            "api_key": "vms_123",
            "authorization": "Bearer xyz",
            "cookie": "session=abc",
            "name": "Test User",
        }
        safe = AuditService._sanitize(payload)
        assert safe["email"] == "user@test.com"
        assert safe["name"] == "Test User"
        assert safe["password"] == "[REDACTED]"
        assert safe["token"] == "[REDACTED]"
        assert safe["secret"] == "[REDACTED]"
        assert safe["api_key"] == "[REDACTED]"
        assert safe["authorization"] == "[REDACTED]"
        assert safe["cookie"] == "[REDACTED]"

    def test_sanitize_nested_dict(self):
        """Sanitização recursiva em dicts aninhados."""
        payload = {
            "user": {
                "email": "user@test.com",
                "password": "secret",
            },
            "action": "login",
        }
        safe = AuditService._sanitize(payload)
        assert safe["user"]["email"] == "user@test.com"
        assert safe["user"]["password"] == "[REDACTED]"
        assert safe["action"] == "login"

    def test_sanitize_empty_dict(self):
        """Sanitização de dict vazio retorna dict vazio."""
        assert AuditService._sanitize({}) == {}

    def test_sanitize_none_payload(self):
        """Sanitização de None retorna dict vazio."""
        assert AuditService._sanitize(None) == {}

    def test_sanitize_case_insensitive(self):
        """Sanitização é case-insensitive."""
        payload = {"PASSWORD": "secret", "Token": "abc", "API_KEY": "vms_123"}
        safe = AuditService._sanitize(payload)
        assert safe["PASSWORD"] == "[REDACTED]"
        assert safe["Token"] == "[REDACTED]"
        assert safe["API_KEY"] == "[REDACTED]"
