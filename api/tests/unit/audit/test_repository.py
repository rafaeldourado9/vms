"""Testes unitários do AuditRepository."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from vms.audit.domain import AuditLog
from vms.audit.models import AuditLogModel
from vms.audit.repository import AuditRepository, _to_domain
from vms.shared.kernel import AuditId, EntityId, TenantId


class TestToDomain:
    """Testes da função _to_domain."""

    def test_converts_model_to_domain(self):
        """_to_domain converte AuditLogModel para AuditLog."""
        model = AuditLogModel(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            user_email="admin@test.com",
            user_role="admin",
            action="camera.created",
            resource_type="camera",
            resource_id=uuid.uuid4(),
            resource_name="Câmera 01",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            request_id=uuid.uuid4(),
            payload={"key": "value"},
            result="success",
            occurred_at=datetime.now(timezone.utc),
        )
        domain = _to_domain(model)
        assert domain.id == model.id
        assert domain.tenant_id == model.tenant_id
        assert domain.user_id == model.user_id
        assert domain.user_email == "admin@test.com"
        assert domain.user_role == "admin"
        assert domain.action == "camera.created"
        assert domain.resource_type == "camera"
        assert domain.resource_id == model.resource_id
        assert domain.resource_name == "Câmera 01"
        assert domain.ip_address == "192.168.1.100"
        assert domain.user_agent == "Mozilla/5.0"
        assert domain.request_id == model.request_id
        assert domain.payload == {"key": "value"}
        assert domain.result == "success"

    def test_to_domain_defaults_payload_to_empty_dict(self):
        """_to_domain com payload=None retorna dict vazio."""
        model = AuditLogModel(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action="test",
            payload=None,
        )
        domain = _to_domain(model)
        assert domain.payload == {}

    def test_to_domain_defaults_result_to_success(self):
        """_to_domain com result=None retorna 'success'."""
        model = AuditLogModel(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action="test",
            result=None,
        )
        domain = _to_domain(model)
        assert domain.result == "success"


class TestAuditRepositoryCreate:
    """Testes de criação no repositório de auditoria."""

    @pytest.fixture
    def session(self):
        """Sessão mockada."""
        session = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, session):
        return AuditRepository(session)

    async def test_create_persists_audit_log(self, repo, session):
        """create() persiste AuditLog e retorna domain entity."""
        audit_log = AuditLog(
            tenant_id=TenantId(uuid.uuid4()),
            action="camera.created",
            user_email="admin@test.com",
        )
        # Simular flush que popula o model
        def mock_add(model):
            if not model.id:
                model.id = uuid.uuid4()
            if not model.occurred_at:
                model.occurred_at = datetime.now(timezone.utc)

        session.add = MagicMock(side_effect=mock_add)

        result = await repo.create(audit_log)
        assert result.action == "camera.created"
        session.flush.assert_called_once()

    async def test_create_preserves_domain_id(self, repo, session):
        """create() preserva o ID do domínio."""
        domain_id = AuditId(uuid.uuid4())
        audit_log = AuditLog(
            id=domain_id,
            tenant_id=TenantId(uuid.uuid4()),
            action="test.action",
        )

        def mock_add(model):
            pass

        session.add = MagicMock(side_effect=mock_add)
        result = await repo.create(audit_log)
        assert str(result.id) == str(domain_id)


class TestAuditRepositoryList:
    """Testes de listagem com filtros — usando mock de alto nível."""

    @pytest.fixture
    def repo(self):
        """Repositório com session completamente mockado."""
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=5)

        # Criar models de teste
        log1 = AuditLogModel(
            id=uuid.uuid4(),
            tenant_id="t1",
            action="camera.created",
            user_email="admin@test.com",
            result="success",
            payload={},
            occurred_at=datetime.now(timezone.utc),
        )
        log2 = AuditLogModel(
            id=uuid.uuid4(),
            tenant_id="t1",
            action="user.deleted",
            user_email="admin@test.com",
            result="success",
            payload={},
            occurred_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        # scalars() retorna objeto síncrono com .all()
        scalar_result = MagicMock()
        scalar_result.all.return_value = [log1, log2]
        session.scalars = AsyncMock(return_value=scalar_result)

        return AuditRepository(session)

    async def test_list_by_tenant_filters_by_tenant(self, repo):
        """list_by_tenant() filtra logs pelo tenant_id."""
        logs, total = await repo.list_by_tenant(tenant_id="t1")
        assert len(logs) == 2
        assert total == 5
        assert all(isinstance(log, AuditLog) for log in logs)

    async def test_list_by_tenant_returns_tuple(self, repo):
        """list_by_tenant() retorna (items, total)."""
        logs, total = await repo.list_by_tenant(tenant_id="t1")
        assert isinstance(logs, list)
        assert isinstance(total, int)
        assert total == 5

    async def test_list_by_tenant_with_action_filter(self, repo):
        """list_by_tenant() filtra por action."""
        logs, total = await repo.list_by_tenant(
            tenant_id="t1",
            action="camera.created",
        )
        assert total == 5

    async def test_list_by_tenant_with_user_id_filter(self, repo):
        """list_by_tenant() filtra por user_id."""
        user_id = str(uuid.uuid4())
        logs, total = await repo.list_by_tenant(
            tenant_id="t1",
            user_id=user_id,
        )
        assert total == 5

    async def test_list_by_tenant_with_resource_type_filter(self, repo):
        """list_by_tenant() filtra por resource_type."""
        logs, total = await repo.list_by_tenant(
            tenant_id="t1",
            resource_type="camera",
        )
        assert total == 5

    async def test_list_by_tenant_with_date_range_filter(self, repo):
        """list_by_tenant() filtra por from_date e to_date."""
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(days=7)
        to_date = now

        logs, total = await repo.list_by_tenant(
            tenant_id="t1",
            from_date=from_date,
            to_date=to_date,
        )
        assert total == 5

    async def test_list_by_tenant_pagination(self, repo):
        """list_by_tenant() aplica limit e offset."""
        logs, total = await repo.list_by_tenant(
            tenant_id="t1",
            limit=10,
            offset=20,
        )
        assert total == 5

    async def test_list_by_tenant_order_by_occurred_at_desc(self, repo):
        """list_by_tenant() ordena por occurred_at DESC."""
        logs, total = await repo.list_by_tenant(tenant_id="t1")
        assert len(logs) == 2
        # Verificar ordem decrescente
        assert logs[0].occurred_at >= logs[1].occurred_at
