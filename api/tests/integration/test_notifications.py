"""Testes de integração — CRUD de regras de notificação e logs."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_data(db_session_factory):
    """Cria tenant + user para testes de notificações."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-notif", name="Test", slug="test-notif")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-notif", tenant_id="t-notif", email="admin@notif.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        await session.commit()
    token = create_access_token("u-notif", "t-notif", "admin")
    return {"token": token, "tenant_id": "t-notif"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestNotificationRules:
    """CRUD regras de notificação — /api/v1/notifications/rules."""

    async def test_create_rule(self, client: AsyncClient, seeded_data, auth_header):
        """POST cria regra de notificação."""
        resp = await client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "ALPR Alert",
                "event_type_pattern": "alpr.*",
                "destination_url": "https://hooks.example.com/vms",
                "webhook_secret": "my-secret-key-1234",
            },
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "ALPR Alert"
        assert data["event_type_pattern"] == "alpr.*"
        assert data["is_active"] is True

    async def test_list_rules(self, client: AsyncClient, seeded_data, auth_header):
        """GET lista regras do tenant."""
        # Cria regra
        await client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "Rule 1",
                "event_type_pattern": "*",
                "destination_url": "https://hooks.example.com/1",
                "webhook_secret": "secret-1234567890",
            },
            headers=auth_header,
        )
        resp = await client.get(
            "/api/v1/notifications/rules",
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_rule(self, client: AsyncClient, seeded_data, auth_header):
        """GET retorna regra por ID."""
        create_resp = await client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "Get Rule",
                "event_type_pattern": "camera.*",
                "destination_url": "https://hooks.example.com/2",
                "webhook_secret": "secret-2345678901",
            },
            headers=auth_header,
        )
        rule_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/notifications/rules/{rule_id}",
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Rule"

    async def test_delete_rule(self, client: AsyncClient, seeded_data, auth_header):
        """DELETE remove regra."""
        create_resp = await client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "To Delete",
                "event_type_pattern": "*",
                "destination_url": "https://hooks.example.com/3",
                "webhook_secret": "secret-3456789012",
            },
            headers=auth_header,
        )
        rule_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/notifications/rules/{rule_id}",
            headers=auth_header,
        )
        assert resp.status_code == 204

        # Verificar que foi removida
        resp = await client.get(
            f"/api/v1/notifications/rules/{rule_id}",
            headers=auth_header,
        )
        assert resp.status_code == 404

    async def test_delete_nonexistent_rule(self, client: AsyncClient, seeded_data, auth_header):
        """DELETE regra inexistente retorna 404."""
        resp = await client.delete(
            "/api/v1/notifications/rules/nonexistent",
            headers=auth_header,
        )
        assert resp.status_code == 404

    async def test_list_rules_no_auth(self, client: AsyncClient):
        """GET sem autenticação retorna 401."""
        resp = await client.get("/api/v1/notifications/rules")
        assert resp.status_code == 401
