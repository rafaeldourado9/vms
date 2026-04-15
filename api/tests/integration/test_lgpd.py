"""Testes de integração do LGPD router.

Nota: Estes testes requerem PostgreSQL (JSONB não é suportado pelo SQLite).
Rodam apenas em ambiente com PostgreSQL real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from vms.infrastructure.security import hash_password
from vms.iam.models import TenantModel, UserModel
from vms.lgpd.domain import (
    ConsentAction,
    ConsentRecord,
    DataType,
    RequestType,
    RetentionPolicy,
)
from vms.lgpd.models import (
    ConsentRecordModel,
    RetentionPolicyModel,
)
from vms.shared.kernel import AuditId, EntityId, TenantId


@pytest.fixture
async def seeded_db_with_lgpd(db_session_factory):
    """Cria tenant + user + registros LGPD."""
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

        # Consent record
        consent = ConsentRecordModel(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            user_id="user-1",
            data_type=DataType.FACE,
            action=ConsentAction.GRANTED,
            consent_text_hash="sha256_hash",
            ip_address="192.168.1.100",
            created_at=datetime.now(timezone.utc),
        )
        session.add(consent)

        # Retention policy
        policy = RetentionPolicyModel(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            data_type=DataType.ALPR,
            retention_days=90,
            anonymize_instead_of_delete=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(policy)

        await session.commit()

    return {"tenant_id": "tenant-1", "user_id": "user-1"}


class TestLGPDConsent:
    """Testes dos endpoints de consentimento LGPD."""

    async def test_get_consent_log(self, client, seeded_db_with_lgpd):
        """GET /api/v1/lgpd/consent-log retorna logs de consentimento."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/lgpd/consent-log",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    async def test_grant_consent(self, client, seeded_db_with_lgpd):
        """POST /api/v1/lgpd/consent registra consentimento."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/lgpd/consent",
            headers={"Authorization": f"Bearer {token}"},
            json={"data_type": "face", "action": "granted"},
        )
        # Pode ser 200 ou 201
        assert resp.status_code in (200, 201)

    async def test_revoke_consent(self, client, seeded_db_with_lgpd):
        """POST /api/v1/lgpd/revoke revoga consentimento."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/lgpd/revoke",
            headers={"Authorization": f"Bearer {token}"},
            json={"data_type": "face"},
        )
        assert resp.status_code in (200, 201)

    async def test_consent_requires_auth(self, client):
        """Endpoints de consentimento requerem autenticação."""
        resp = await client.get("/api/v1/lgpd/consent-log")
        assert resp.status_code == 401


class TestLGPDRetentionPolicies:
    """Testes dos endpoints de políticas de retenção."""

    async def test_get_retention_policies(self, client, seeded_db_with_lgpd):
        """GET /api/v1/lgpd/retention-policies retorna políticas."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/lgpd/retention-policies",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


class TestLGPDDataSubjectRequests:
    """Testes dos endpoints de solicitação do titular."""

    async def test_create_data_export_request(self, client, seeded_db_with_lgpd):
        """POST /api/v1/lgpd/data-export cria solicitação."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/lgpd/data-export",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201)

    async def test_create_data_deletion_request(self, client, seeded_db_with_lgpd):
        """POST /api/v1/lgpd/data-deletion cria solicitação de deleção."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/lgpd/data-deletion",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code in (200, 201)
