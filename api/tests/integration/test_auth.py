"""Testes de integração da autenticação — endpoints HTTP."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_db(db_session_factory):
    """Cria tenant + user no banco para testes de auth."""
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
        await session.commit()
    return {"tenant_id": "tenant-1", "user_id": "user-1"}


class TestLogin:
    """POST /api/v1/auth/token"""

    async def test_login_ok(self, client: AsyncClient, seeded_db):
        """Login com credenciais válidas retorna tokens."""
        resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password(self, client: AsyncClient, seeded_db):
        """Login com senha errada retorna 401."""
        resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "errada12345"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient, seeded_db):
        """Login com email inexistente retorna 401."""
        resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "nobody@test.com", "password": "senha12345"},
        )
        assert resp.status_code == 401

    async def test_login_invalid_email_format(self, client: AsyncClient):
        """Login com email inválido retorna 422."""
        resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "not-an-email", "password": "senha12345"},
        )
        assert resp.status_code == 422

    async def test_login_short_password(self, client: AsyncClient):
        """Login com senha curta retorna 422."""
        resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "short"},
        )
        assert resp.status_code == 422


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_ok(self, client: AsyncClient, seeded_db):
        """Refresh com token válido retorna novos tokens."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        """Refresh com token inválido retorna 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert resp.status_code == 401


class TestGetMe:
    """GET /api/v1/users/me"""

    async def test_get_me_ok(self, client: AsyncClient, seeded_db):
        """Retorna dados do usuário autenticado."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@test.com"
        assert data["role"] == "admin"
        assert data["tenant_id"] == "tenant-1"

    async def test_get_me_no_token(self, client: AsyncClient):
        """Sem token retorna 401."""
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        """Token inválido retorna 401."""
        resp = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401
