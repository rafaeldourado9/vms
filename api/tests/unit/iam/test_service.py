"""Testes unitários dos services IAM com repos mockados."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from vms.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from vms.core.security import hash_password
from vms.iam.domain import ApiKey, ApiKeyOwnerType, Tenant, User, UserRole
from vms.iam.service import ApiKeyService, AuthService, TenantService, UserService


# ─── TenantService ───────────────────────────────────────────────────────────


class TestTenantService:
    """Testes do TenantService."""

    @pytest.fixture
    def tenant_repo(self):
        repo = AsyncMock()
        repo.get_by_slug = AsyncMock(return_value=None)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.create = AsyncMock(side_effect=lambda t: t)
        return repo

    @pytest.fixture
    def svc(self, tenant_repo):
        return TenantService(tenant_repo)

    async def test_create_tenant_ok(self, svc, tenant_repo):
        """Cria tenant quando slug é único."""
        result = await svc.create_tenant("Acme", "acme")
        assert result.name == "Acme"
        assert result.slug == "acme"
        tenant_repo.create.assert_called_once()

    async def test_create_tenant_slug_conflict(self, svc, tenant_repo):
        """Lança ConflictError se slug já existe."""
        tenant_repo.get_by_slug.return_value = Tenant(
            id="x", name="Existing", slug="acme"
        )
        with pytest.raises(ConflictError, match="acme"):
            await svc.create_tenant("Acme", "acme")

    async def test_get_tenant_ok(self, svc, tenant_repo):
        """Retorna tenant quando existe."""
        expected = Tenant(id="t1", name="Acme", slug="acme")
        tenant_repo.get_by_id.return_value = expected
        result = await svc.get_tenant("t1")
        assert result.id == "t1"

    async def test_get_tenant_not_found(self, svc, tenant_repo):
        """Lança NotFoundError quando tenant não existe."""
        tenant_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await svc.get_tenant("xxx")


# ─── UserService ──────────────────────────────────────────────────────────────


class TestUserService:
    """Testes do UserService."""

    @pytest.fixture
    def tenant_repo(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(
            return_value=Tenant(id="t1", name="Acme", slug="acme")
        )
        return repo

    @pytest.fixture
    def user_repo(self):
        repo = AsyncMock()
        repo.get_by_email = AsyncMock(return_value=None)
        repo.get_by_id = AsyncMock(return_value=None)
        repo.create = AsyncMock(side_effect=lambda u: u)
        return repo

    @pytest.fixture
    def svc(self, user_repo, tenant_repo):
        return UserService(user_repo, tenant_repo)

    async def test_create_user_ok(self, svc, user_repo):
        """Cria usuário com dados válidos."""
        result = await svc.create_user(
            "t1", "user@test.com", "senha12345", "Test User", UserRole.OPERATOR
        )
        assert result.email == "user@test.com"
        assert result.role == UserRole.OPERATOR
        user_repo.create.assert_called_once()

    async def test_create_user_email_conflict(self, svc, user_repo):
        """Lança ConflictError se email já existe no tenant."""
        user_repo.get_by_email.return_value = User(
            id="x",
            tenant_id="t1",
            email="user@test.com",
            hashed_password="h",
            full_name="Existing",
            role=UserRole.VIEWER,
        )
        with pytest.raises(ConflictError, match="user@test.com"):
            await svc.create_user(
                "t1", "user@test.com", "senha12345", "Test", UserRole.VIEWER
            )

    async def test_create_user_tenant_not_found(self, svc, tenant_repo):
        """Lança NotFoundError se tenant não existe."""
        tenant_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError, match="Tenant"):
            await svc.create_user(
                "xxx", "user@test.com", "senha12345", "Test", UserRole.VIEWER
            )

    async def test_get_user_ok(self, svc, user_repo):
        """Retorna usuário quando existe."""
        expected = User(
            id="u1",
            tenant_id="t1",
            email="a@b.com",
            hashed_password="h",
            full_name="Test",
            role=UserRole.ADMIN,
        )
        user_repo.get_by_id.return_value = expected
        result = await svc.get_user("u1", "t1")
        assert result.id == "u1"

    async def test_get_user_not_found(self, svc, user_repo):
        """Lança NotFoundError quando usuário não existe."""
        user_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await svc.get_user("xxx", "t1")


# ─── AuthService ──────────────────────────────────────────────────────────────


class TestAuthService:
    """Testes do AuthService."""

    @pytest.fixture
    def user_repo(self):
        repo = AsyncMock()
        hashed = hash_password("senha12345")
        repo.get_by_email = AsyncMock(
            return_value=User(
                id="u1",
                tenant_id="t1",
                email="user@test.com",
                hashed_password=hashed,
                full_name="Test",
                role=UserRole.ADMIN,
            )
        )
        repo.get_by_id = AsyncMock(
            return_value=User(
                id="u1",
                tenant_id="t1",
                email="user@test.com",
                hashed_password=hashed,
                full_name="Test",
                role=UserRole.ADMIN,
            )
        )
        return repo

    @pytest.fixture
    def api_key_repo(self):
        return AsyncMock()

    @pytest.fixture
    def svc(self, user_repo, api_key_repo):
        return AuthService(user_repo, api_key_repo)

    async def test_authenticate_user_ok(self, svc):
        """Login com credenciais válidas retorna tokens."""
        access, refresh = await svc.authenticate_user(
            "user@test.com", "senha12345", "t1"
        )
        assert access
        assert refresh
        assert access != refresh

    async def test_authenticate_user_wrong_password(self, svc):
        """Login com senha errada lança AuthenticationError."""
        with pytest.raises(AuthenticationError):
            await svc.authenticate_user("user@test.com", "errada", "t1")

    async def test_authenticate_user_not_found(self, svc, user_repo):
        """Login com email inexistente lança AuthenticationError."""
        user_repo.get_by_email.return_value = None
        with pytest.raises(AuthenticationError):
            await svc.authenticate_user("nope@test.com", "x", "t1")

    async def test_authenticate_user_inactive(self, svc, user_repo):
        """Login com usuário inativo lança AuthenticationError."""
        user = user_repo.get_by_email.return_value
        user.is_active = False
        with pytest.raises(AuthenticationError):
            await svc.authenticate_user("user@test.com", "senha12345", "t1")

    async def test_refresh_token_ok(self, svc):
        """Refresh com token válido retorna novos tokens."""
        from vms.core.security import create_refresh_token

        refresh = create_refresh_token("u1", "t1")
        access, new_refresh = await svc.refresh_access_token(refresh)
        assert access
        assert new_refresh

    async def test_refresh_token_invalid(self, svc):
        """Refresh com token inválido lança AuthenticationError."""
        with pytest.raises(AuthenticationError):
            await svc.refresh_access_token("token-invalido")

    async def test_refresh_with_access_token_fails(self, svc):
        """Usar access token como refresh lança AuthenticationError."""
        from vms.core.security import create_access_token

        access = create_access_token("u1", "t1", "admin")
        with pytest.raises(AuthenticationError):
            await svc.refresh_access_token(access)


# ─── ApiKeyService ───────────────────────────────────────────────────────────


class TestApiKeyService:
    """Testes do ApiKeyService."""

    @pytest.fixture
    def api_key_repo(self):
        repo = AsyncMock()
        repo.create = AsyncMock(side_effect=lambda k: k)
        repo.revoke = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def svc(self, api_key_repo):
        return ApiKeyService(api_key_repo)

    async def test_issue_api_key(self, svc, api_key_repo):
        """Emissão de API key retorna entidade e plain key."""
        api_key, plain = await svc.issue_api_key(
            "t1", ApiKeyOwnerType.AGENT, "agent-1"
        )
        assert plain.startswith("vms_")
        assert api_key.owner_type == ApiKeyOwnerType.AGENT
        api_key_repo.create.assert_called_once()

    async def test_revoke_api_key_ok(self, svc, api_key_repo):
        """Revogação bem-sucedida não lança exceção."""
        await svc.revoke_api_key("k1", "t1")
        api_key_repo.revoke.assert_called_once_with("k1", "t1")

    async def test_revoke_api_key_not_found(self, svc, api_key_repo):
        """Revogação de key inexistente lança NotFoundError."""
        api_key_repo.revoke.return_value = False
        with pytest.raises(NotFoundError):
            await svc.revoke_api_key("xxx", "t1")
