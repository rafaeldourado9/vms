"""Testes unitários do Billing domain — VmsLicense, License, LicenseType, etc."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from vms.billing.domain import (
    DeploymentModel,
    License,
    LicenseCreated,
    LicenseExpired,
    LicenseStatus,
    LicenseType,
    LicenseValidation,
    VmsLicense,
)
from vms.shared.kernel import BillingId, TenantId


# ─── VmsLicense (Whitelabel activation) ───────────────────────────────────────


class TestVmsLicense:
    """Testes da entidade VmsLicense (whitelabel activation)."""

    def test_create_managed_license(self):
        """Licença managed com defaults corretos."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.MANAGED,
        )
        assert lic.deployment_model == DeploymentModel.MANAGED
        assert lic.status == LicenseStatus.ACTIVE
        assert lic.max_cameras == 0
        assert lic.is_valid is True

    def test_create_self_hosted_license(self):
        """Licença self-hosted com preço diferente."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.SELF_HOSTED,
        )
        assert lic.annual_price == 20000.00
        assert lic.storage_monthly_per_camera is None

    def test_managed_annual_price(self):
        """Managed = R$ 15.000/ano."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.MANAGED,
        )
        assert lic.annual_price == 15000.00

    def test_managed_storage_monthly_per_camera(self):
        """Managed storage = R$ 50/cam/mês."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.MANAGED,
        )
        assert lic.storage_monthly_per_camera == 50.00

    def test_is_valid_active(self):
        """Licença ativa e não expirada é válida."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            status=LicenseStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        assert lic.is_valid is True

    def test_is_valid_expired_status(self):
        """Licença com status EXPIRED não é válida."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            status=LicenseStatus.EXPIRED,
        )
        assert lic.is_valid is False

    def test_is_valid_revoked(self):
        """Licença REVOKED não é válida."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            status=LicenseStatus.REVOKED,
        )
        assert lic.is_valid is False

    def test_is_valid_past_expires_at(self):
        """Licença com expires_at no passado não é válida."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            status=LicenseStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert lic.is_valid is False

    def test_is_valid_no_expires_at(self):
        """Licença sem expires_at é válida (perpetual)."""
        lic = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            status=LicenseStatus.ACTIVE,
            expires_at=None,
        )
        assert lic.is_valid is True

    def test_generate_key_format(self):
        """generate_key retorna formato XXXX-XXXXX-XXXXX-XXXXX-XXXXX."""
        key = VmsLicense.generate_key()
        parts = key.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 4
        assert len(parts[1]) == 5
        assert len(parts[2]) == 5
        assert len(parts[3]) == 5
        assert len(parts[4]) == 5

    def test_generate_key_unique(self):
        """Cada chamada gera key única."""
        key1 = VmsLicense.generate_key()
        key2 = VmsLicense.generate_key()
        assert key1 != key2

    def test_verify_key_format_valid(self):
        """verify_key_format aceita formato correto."""
        assert VmsLicense.verify_key_format("ABCD-12345-ABCDE-67890-FGHIJ") is True

    def test_verify_key_format_invalid(self):
        """verify_key_format rejeita formato incorreto."""
        assert VmsLicense.verify_key_format("invalid") is False
        assert VmsLicense.verify_key_format("ABCD-12345-ABCDE-67890") is False
        assert VmsLicense.verify_key_format("abcd-12345-abcde-67890-fghij") is False

    def test_fingerprint_is_deterministic(self):
        """fingerprint é determinístico para mesmos dados."""
        lic1 = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.MANAGED,
            hardware_id="HW123",
            customer_email="test@test.com",
        )
        lic2 = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            deployment_model=DeploymentModel.MANAGED,
            hardware_id="HW123",
            customer_email="test@test.com",
        )
        assert lic1.fingerprint() == lic2.fingerprint()

    def test_fingerprint_changes_with_different_email(self):
        """fingerprint muda com email diferente."""
        lic1 = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            customer_email="a@test.com",
        )
        lic2 = VmsLicense(
            license_key="VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW",
            customer_email="b@test.com",
        )
        assert lic1.fingerprint() != lic2.fingerprint()


# ─── License (per-camera) ───────────────────────────────────────────────────


class TestLicense:
    """Testes da entidade License (per-camera licensing)."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    def test_create_camera_only_license(self, tenant_id):
        """Licença CAMERA_ONLY criada com defaults."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        assert lic.license_type == LicenseType.CAMERA_ONLY
        assert lic.status == LicenseStatus.ACTIVE
        assert lic.analytics_enabled is False
        assert lic.storage_limit_gb is None

    def test_create_camera_analytics_license(self, tenant_id):
        """Licença CAMERA_ANALYTICS com analytics_enabled."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ANALYTICS,
            analytics_enabled=True,
        )
        assert lic.has_analytics is True

    def test_camera_only_no_analytics(self, tenant_id):
        """CAMERA_ONLY não tem analytics mesmo se flag=True."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
            analytics_enabled=True,  # ignorado para CAMERA_ONLY
        )
        assert lic.has_analytics is False

    def test_is_active_true(self, tenant_id):
        """Licença ativa e não expirada."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            status=LicenseStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        )
        assert lic.is_active is True

    def test_is_active_false_expired_status(self, tenant_id):
        """Licença com status EXPIRED."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            status=LicenseStatus.EXPIRED,
        )
        assert lic.is_active is False

    def test_is_active_false_past_date(self, tenant_id):
        """Licença com expires_at no passado."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            status=LicenseStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert lic.is_active is False

    def test_is_active_false_no_expiry(self, tenant_id):
        """Licença sem expires_at é ativa."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
            status=LicenseStatus.ACTIVE,
            expires_at=None,
        )
        assert lic.is_active is True

    def test_expire(self, tenant_id):
        """expire() muda status e emite evento."""
        lic = License(
            tenant_id=tenant_id,
            camera_id="cam-1",
        )
        lic.expire()
        assert lic.status == LicenseStatus.EXPIRED
        events = lic.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], LicenseExpired)
        assert events[0].camera_id == "cam-1"

    def test_license_without_camera_id(self, tenant_id):
        """Licença sem camera_id (avulsa)."""
        lic = License(
            tenant_id=tenant_id,
            camera_id=None,
        )
        assert lic.camera_id is None


# ─── LicenseValidation ──────────────────────────────────────────────────────


class TestLicenseValidation:
    """Testes da entidade LicenseValidation."""

    def test_valid_validation(self):
        """Validation com is_valid=True."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
        )
        validation = LicenseValidation(is_valid=True, license=lic)
        assert validation.is_valid is True
        assert validation.license is lic
        assert validation.reason == ""

    def test_invalid_validation_with_reason(self):
        """Validation com is_valid=False e reason."""
        validation = LicenseValidation(
            is_valid=False,
            reason="Nenhuma licença encontrada",
        )
        assert validation.is_valid is False
        assert validation.license is None
        assert validation.reason == "Nenhuma licença encontrada"


# ─── Domain Events ──────────────────────────────────────────────────────────


class TestLicenseEvents:
    """Testes dos domain events de licença."""

    def test_license_created_event(self):
        """LicenseCreated com dados corretos."""
        event = LicenseCreated(
            license_id=BillingId(uuid.uuid4()),
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ANALYTICS,
        )
        assert event.camera_id == "cam-1"
        assert event.license_type == LicenseType.CAMERA_ANALYTICS

    def test_license_expired_event(self):
        """LicenseExpired com dados corretos."""
        event = LicenseExpired(
            license_id=BillingId(uuid.uuid4()),
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
        )
        assert event.camera_id == "cam-1"


# ─── Enums ──────────────────────────────────────────────────────────────────


class TestLicenseEnums:
    """Testes dos enums de licenciamento."""

    def test_license_type_values(self):
        """LicenseType tem valores corretos."""
        assert LicenseType.CAMERA_ONLY == "camera_only"
        assert LicenseType.CAMERA_STORAGE == "camera_storage"
        assert LicenseType.CAMERA_ANALYTICS == "camera_analytics"

    def test_license_status_values(self):
        """LicenseStatus tem valores corretos."""
        assert LicenseStatus.ACTIVE == "active"
        assert LicenseStatus.EXPIRED == "expired"
        assert LicenseStatus.REVOKED == "revoked"

    def test_deployment_model_values(self):
        """DeploymentModel tem valores corretos."""
        assert DeploymentModel.MANAGED == "managed"
        assert DeploymentModel.SELF_HOSTED == "self_hosted"
