"""Testes unitários das entidades de domínio do IAM."""
import pytest

from vms.iam.domain import ApiKey, ApiKeyOwnerType, Tenant, User, UserRole


class TestTenant:
    """Testes da entidade Tenant."""

    def test_create_tenant_defaults(self):
        """Tenant criado com defaults corretos."""
        tenant = Tenant(id="t1", name="Acme", slug="acme")
        assert tenant.is_active is True
        assert tenant.facial_recognition_enabled is False
        assert tenant.facial_recognition_consent_at is None

    def test_enable_facial_recognition(self):
        """Habilitar face recognition registra consentimento."""
        from datetime import datetime, UTC
        tenant = Tenant(id="t1", name="Acme", slug="acme")
        now = datetime.now(UTC)
        tenant.enable_facial_recognition(now)
        assert tenant.facial_recognition_enabled is True
        assert tenant.facial_recognition_consent_at == now


class TestUser:
    """Testes da entidade User."""

    def test_create_user_defaults(self):
        """User criado com defaults corretos."""
        user = User(
            id="u1",
            tenant_id="t1",
            email="a@b.com",
            hashed_password="hash",
            full_name="Test",
            role=UserRole.VIEWER,
        )
        assert user.is_active is True

    @pytest.mark.parametrize(
        "user_role,required_role,expected",
        [
            (UserRole.ADMIN, UserRole.ADMIN, True),
            (UserRole.ADMIN, UserRole.OPERATOR, True),
            (UserRole.ADMIN, UserRole.VIEWER, True),
            (UserRole.OPERATOR, UserRole.ADMIN, False),
            (UserRole.OPERATOR, UserRole.OPERATOR, True),
            (UserRole.OPERATOR, UserRole.VIEWER, True),
            (UserRole.VIEWER, UserRole.ADMIN, False),
            (UserRole.VIEWER, UserRole.OPERATOR, False),
            (UserRole.VIEWER, UserRole.VIEWER, True),
        ],
    )
    def test_has_permission_hierarchy(self, user_role, required_role, expected):
        """Hierarquia de permissões: admin > operator > viewer."""
        user = User(
            id="u1",
            tenant_id="t1",
            email="a@b.com",
            hashed_password="hash",
            full_name="Test",
            role=user_role,
        )
        assert user.has_permission(required_role) is expected


class TestApiKey:
    """Testes da entidade ApiKey."""

    def test_create_api_key_defaults(self):
        """ApiKey criada com defaults corretos."""
        key = ApiKey(
            id="k1",
            tenant_id="t1",
            owner_type=ApiKeyOwnerType.AGENT,
            owner_id="a1",
            key_hash="hash",
            prefix="vms_abc12345",
        )
        assert key.is_active is True
        assert key.last_used_at is None

    def test_revoke(self):
        """Revogar API key desativa permanentemente."""
        key = ApiKey(
            id="k1",
            tenant_id="t1",
            owner_type=ApiKeyOwnerType.AGENT,
            owner_id="a1",
            key_hash="hash",
            prefix="vms_abc12345",
        )
        key.revoke()
        assert key.is_active is False


class TestEnums:
    """Testes dos enums do IAM."""

    def test_user_roles(self):
        assert UserRole.ADMIN == "admin"
        assert UserRole.OPERATOR == "operator"
        assert UserRole.VIEWER == "viewer"

    def test_api_key_owner_types(self):
        assert ApiKeyOwnerType.AGENT == "agent"
        assert ApiKeyOwnerType.ANALYTICS == "analytics"
        assert ApiKeyOwnerType.WEBHOOK == "webhook"
