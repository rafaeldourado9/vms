"""Testes de integração do endpoint de auditoria."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from vms.audit.models import AuditLogModel
from vms.infrastructure.security import hash_password
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_db_with_audit(db_session_factory):
    """Cria tenant + user + audit logs no banco."""
    async with db_session_factory() as session:
        tenant = TenantModel(
            id="tenant-1",
            name="Test Tenant",
            slug="test",
        )
        session.add(tenant)
        await session.flush()

        user = UserModel(
            id="user-1",
            tenant_id="tenant-1",
            email="admin@test.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin User",
            role="admin",
        )
        session.add(user)

        # Criar logs de auditoria de teste
        now = datetime.now(timezone.utc)
        for i in range(5):
            log = AuditLogModel(
                id=uuid.uuid4(),
                tenant_id="tenant-1",
                user_id="user-1",
                user_email="admin@test.com",
                user_role="admin",
                action=f"camera.{['created', 'updated', 'deleted', 'viewed', 'exported'][i]}",
                resource_type="camera",
                resource_id=uuid.uuid4(),
                resource_name=f"Câmera {i + 1}",
                ip_address=f"192.168.1.{100 + i}",
                result="success",
                payload={"detail": f"Log {i + 1}"},
                occurred_at=now - timedelta(hours=i),
            )
            session.add(log)

        # Tenant diferente (para testar isolamento)
        tenant2 = TenantModel(
            id="tenant-2",
            name="Other Tenant",
            slug="other",
        )
        session.add(tenant2)
        await session.flush()

        user2 = UserModel(
            id="user-2",
            tenant_id="tenant-2",
            email="user@other.com",
            hashed_password=hash_password("senha12345"),
            full_name="Other User",
            role="viewer",
        )
        session.add(user2)

        # Log do tenant 2 (não deve aparecer para tenant 1)
        session.add(AuditLogModel(
            id=uuid.uuid4(),
            tenant_id="tenant-2",
            user_id="user-2",
            user_email="user@other.com",
            user_role="viewer",
            action="user.login",
            resource_type="user",
            result="success",
            payload={},
            occurred_at=now,
        ))

        await session.commit()
    return {"tenant_id": "tenant-1", "user_id": "user-1"}


class TestAuditLogsEndpoint:
    """GET /api/v1/audit/logs"""

    async def test_list_audit_logs_ok(self, client: AsyncClient, seeded_db_with_audit):
        """Lista logs do tenant autenticado."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] == 5
        assert len(data["items"]) == 5
        # Verificar estrutura dos items
        item = data["items"][0]
        assert "id" in item
        assert "action" in item
        assert "user_email" in item
        assert "resource_type" in item
        assert "occurred_at" in item
        assert "result" in item

    async def test_list_audit_logs_filters_by_action(self, client: AsyncClient, seeded_db_with_audit):
        """Filtra logs por action."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/audit/logs?action=camera.created",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Todos os items filtrados devem ter action=camera.created
        for item in data["items"]:
            assert item["action"] == "camera.created"

    async def test_list_audit_logs_filters_by_resource_type(self, client: AsyncClient, seeded_db_with_audit):
        """Filtra logs por resource_type."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/audit/logs?resource_type=camera",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resource_type"] == "camera"

    async def test_list_audit_logs_pagination(self, client: AsyncClient, seeded_db_with_audit):
        """Paginação funciona corretamente."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        # Página 1 com 2 items
        resp = await client.get(
            "/api/v1/audit/logs?page=1&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5

        # Página 2
        resp = await client.get(
            "/api/v1/audit/logs?page=2&page_size=2",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 2
        assert len(data["items"]) == 2

    async def test_list_audit_logs_no_token_returns_401(self, client: AsyncClient):
        """Sem token retorna 401."""
        resp = await client.get("/api/v1/audit/logs")
        assert resp.status_code == 401

    async def test_list_audit_logs_tenant_isolation(self, client: AsyncClient, seeded_db_with_audit):
        """Tenant 1 não vê logs do Tenant 2."""
        # Login como tenant-1
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verificar que todos os logs são do tenant-1
        for item in data["items"]:
            assert item["tenant_id"] == "tenant-1"
            # Nenhum log do tenant-2 deve aparecer
            assert item["user_email"] != "user@other.com"

    async def test_list_audit_logs_date_range_filter(self, client: AsyncClient, seeded_db_with_audit):
        """Filtra logs por range de datas."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        now = datetime.now(timezone.utc).isoformat()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        resp = await client.get(
            f"/api/v1/audit/logs?from={yesterday}&to={now}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Todos os logs devem estar dentro do range
        for item in data["items"]:
            occurred = datetime.fromisoformat(item["occurred_at"])
            assert datetime.fromisoformat(yesterday) <= occurred <= datetime.fromisoformat(now)

    async def test_list_audit_logs_ordered_by_occurred_at_desc(self, client: AsyncClient, seeded_db_with_audit):
        """Logs retornados ordenados por occurred_at DESC."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/audit/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        items = data["items"]
        # Verificar que occurred_at está em ordem decrescente
        for i in range(len(items) - 1):
            t1 = datetime.fromisoformat(items[i]["occurred_at"])
            t2 = datetime.fromisoformat(items[i + 1]["occurred_at"])
            assert t1 >= t2
