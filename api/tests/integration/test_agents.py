"""Testes de integração — agents, config e heartbeat."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_data(db_session_factory):
    """Cria tenant + user."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-agent", name="Test", slug="test-agent")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-agent", tenant_id="t-agent", email="admin@agent.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        await session.commit()
    token = create_access_token("u-agent", "t-agent", "admin")
    return {"token": token, "tenant_id": "t-agent"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestAgentsCRUD:
    """CRUD de agents — /api/v1/agents."""

    async def test_create_agent(self, client: AsyncClient, seeded_data, auth_header):
        """POST /agents cria agent e retorna API key."""
        resp = await client.post(
            "/api/v1/agents",
            json={"name": "Agent Portaria"},
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Agent Portaria"
        assert data["status"] == "pending"
        assert "api_key" in data
        assert data["api_key"].startswith("vms_")

    async def test_list_agents(self, client: AsyncClient, seeded_data, auth_header):
        """GET /agents retorna lista."""
        await client.post(
            "/api/v1/agents",
            json={"name": "Agent 1"},
            headers=auth_header,
        )
        resp = await client.get("/api/v1/agents", headers=auth_header)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestAgentHeartbeatAndConfig:
    """Agent config e heartbeat via API key."""

    async def test_heartbeat(self, client: AsyncClient, seeded_data, auth_header):
        """POST /agents/me/heartbeat atualiza status do agent."""
        # Cria agent e pega API key
        create_resp = await client.post(
            "/api/v1/agents",
            json={"name": "Agent HB"},
            headers=auth_header,
        )
        api_key = create_resp.json()["api_key"]

        # Heartbeat
        resp = await client.post(
            "/api/v1/agents/me/heartbeat",
            json={
                "version": "1.0.0",
                "streams_running": 3,
                "streams_failed": 0,
                "uptime_seconds": 1234,
            },
            headers={"Authorization": f"ApiKey {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert data["version"] == "1.0.0"
        assert data["streams_running"] == 3

    async def test_config(self, client: AsyncClient, seeded_data, auth_header):
        """GET /agents/me/config retorna configuração."""
        create_resp = await client.post(
            "/api/v1/agents",
            json={"name": "Agent Config"},
            headers=auth_header,
        )
        api_key = create_resp.json()["api_key"]

        resp = await client.get(
            "/api/v1/agents/me/config",
            headers={"Authorization": f"ApiKey {api_key}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data
        assert "cameras" in data
        assert isinstance(data["cameras"], list)

    async def test_heartbeat_invalid_key(self, client: AsyncClient):
        """Heartbeat com API key inválida retorna 401."""
        resp = await client.post(
            "/api/v1/agents/me/heartbeat",
            json={
                "version": "1.0.0",
                "streams_running": 0,
                "streams_failed": 0,
                "uptime_seconds": 0,
            },
            headers={"Authorization": "ApiKey vms_invalid123"},
        )
        assert resp.status_code == 401
