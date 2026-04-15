"""Testes unitários do LicenseService — criação, validação, quota checks."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from vms.billing.domain import (
    License,
    LicenseCreated,
    LicenseStatus,
    LicenseType,
    LicenseValidation,
)
from vms.billing.repository import LicenseRepositoryPort
from vms.billing.service import LicenseService, QuotaExceededError, DEFAULT_QUOTAS
from vms.shared.kernel import BillingId, TenantId


class TestLicenseService:
    """Testes do LicenseService."""

    @pytest.fixture
    def repo(self):
        repo = AsyncMock(spec=LicenseRepositoryPort)

        async def fake_create(lic: License) -> License:
            return lic

        repo.create = AsyncMock(side_effect=fake_create)
        repo.get_by_camera = AsyncMock(return_value=None)
        repo.get_active_by_tenant = AsyncMock(return_value=[])
        repo.count_active_by_tenant = AsyncMock(return_value=0)
        repo.validate_camera = AsyncMock(
            return_value=LicenseValidation(is_valid=False, reason="Nenhuma licença")
        )
        return repo

    @pytest.fixture
    def svc(self, repo):
        return LicenseService(repo)

    async def test_create_license_camera_only(self, svc, repo):
        """Cria licença CAMERA_ONLY."""
        result = await svc.create_license(
            tenant_id="t1",
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
            duration_days=365,
        )
        assert result.license_type == LicenseType.CAMERA_ONLY
        assert result.camera_id == "cam-1"
        assert result.analytics_enabled is False
        assert result.storage_limit_gb is None
        repo.create.assert_called_once()

    async def test_create_license_analytics(self, svc, repo):
        """Cria licença CAMERA_ANALYTICS com analytics_enabled."""
        result = await svc.create_license(
            tenant_id="t1",
            camera_id="cam-2",
            license_type=LicenseType.CAMERA_ANALYTICS,
            analytics_enabled=True,
        )
        assert result.license_type == LicenseType.CAMERA_ANALYTICS
        assert result.analytics_enabled is True
        assert result.has_analytics is True

    async def test_create_license_storage(self, svc, repo):
        """Cria licença CAMERA_STORAGE com storage_limit_gb."""
        result = await svc.create_license(
            tenant_id="t1",
            camera_id="cam-3",
            license_type=LicenseType.CAMERA_STORAGE,
            storage_limit_gb=500,
        )
        assert result.license_type == LicenseType.CAMERA_STORAGE
        assert result.storage_limit_gb == 500

    async def test_create_license_emits_event(self, svc):
        """create_license emite LicenseCreated."""
        result = await svc.create_license(
            tenant_id="t1",
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        events = result.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], LicenseCreated)
        assert events[0].camera_id == "cam-1"

    async def test_create_license_without_camera(self, svc):
        """Cria licença avulsa sem camera_id."""
        result = await svc.create_license(
            tenant_id="t1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        assert result.camera_id is None

    async def test_create_license_default_duration(self, svc):
        """create_license usa 365 dias por default."""
        result = await svc.create_license(
            tenant_id="t1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        assert result.expires_at is not None
        # Deve estar entre 364 e 366 dias a partir de agora
        diff = result.expires_at - datetime.utcnow()
        assert 364 <= diff.days <= 366

    async def test_validate_camera_valid(self, svc, repo):
        """validate_camera retorna válido quando licença existe."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        repo.validate_camera = AsyncMock(
            return_value=LicenseValidation(is_valid=True, license=lic)
        )
        result = await svc.validate_camera("cam-1", "t1")
        assert result.is_valid is True

    async def test_validate_camera_invalid(self, svc, repo):
        """validate_camera retorna inválido quando sem licença."""
        repo.validate_camera = AsyncMock(
            return_value=LicenseValidation(is_valid=False, reason="Nenhuma licença")
        )
        result = await svc.validate_camera("cam-99", "t1")
        assert result.is_valid is False
        assert result.reason == "Nenhuma licença"

    async def test_check_analytics_allowed_true(self, svc, repo):
        """check_analytics_allowed retorna True para licença analytics."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ANALYTICS,
            analytics_enabled=True,
        )
        repo.validate_camera = AsyncMock(
            return_value=LicenseValidation(is_valid=True, license=lic)
        )
        result = await svc.check_analytics_allowed("cam-1", "t1")
        assert result is True

    async def test_check_analytics_allowed_false(self, svc, repo):
        """check_analytics_allowed retorna False sem licença analytics."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        repo.validate_camera = AsyncMock(
            return_value=LicenseValidation(is_valid=True, license=lic)
        )
        result = await svc.check_analytics_allowed("cam-1", "t1")
        assert result is False

    async def test_get_tenant_license_summary(self, svc, repo):
        """get_tenant_license_summary retorna dados agregados."""
        lic1 = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-1",
            license_type=LicenseType.CAMERA_ONLY,
        )
        lic2 = License(
            tenant_id=TenantId(uuid.uuid4()),
            camera_id="cam-2",
            license_type=LicenseType.CAMERA_ANALYTICS,
            analytics_enabled=True,
        )
        repo.get_active_by_tenant = AsyncMock(return_value=[lic1, lic2])
        repo.count_active_by_tenant = AsyncMock(return_value=2)

        result = await svc.get_tenant_license_summary("t1")
        assert result["total_active"] == 2
        assert len(result["licenses"]) == 2
        assert result["by_type"][LicenseType.CAMERA_ONLY] == 1
        assert result["by_type"][LicenseType.CAMERA_ANALYTICS] == 1


class TestQuotaChecks:
    """Testes de verificações de quota."""

    @pytest.fixture
    def repo(self):
        repo = AsyncMock(spec=LicenseRepositoryPort)
        repo.get_active_by_tenant = AsyncMock(return_value=[])
        repo.count_active_by_tenant = AsyncMock(return_value=0)
        return repo

    @pytest.fixture
    def svc(self, repo):
        return LicenseService(repo)

    async def test_camera_quota_with_licenses(self, svc, repo):
        """check_camera_quota com licenças existentes."""
        repo.count_active_by_tenant = AsyncMock(return_value=3)
        result = await svc.check_camera_quota("t1")
        assert result["allowed"] is True
        assert result["current"] == 3
        assert result["limit"] == 3
        assert result["pct"] == 100.0

    async def test_camera_quota_no_licenses(self, svc, repo):
        """check_camera_quota sem licenças."""
        repo.count_active_by_tenant = AsyncMock(return_value=0)
        result = await svc.check_camera_quota("t1")
        assert result["allowed"] is False
        assert result["current"] == 0
        assert result["limit"] == 0

    async def test_storage_quota_within_limit(self, svc, repo):
        """check_storage_quota dentro do limite."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            license_type=LicenseType.CAMERA_STORAGE,
            storage_limit_gb=500,
        )
        repo.get_active_by_tenant = AsyncMock(return_value=[lic])
        result = await svc.check_storage_quota("t1", current_storage_gb=100.0)
        assert result["allowed"] is True
        assert result["current"] == 100.0
        assert result["limit"] == 500.0
        assert result["pct"] == 20.0

    async def test_storage_quota_exceeded(self, svc, repo):
        """check_storage_quota excedido."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            license_type=LicenseType.CAMERA_STORAGE,
            storage_limit_gb=500,
        )
        repo.get_active_by_tenant = AsyncMock(return_value=[lic])
        result = await svc.check_storage_quota("t1", current_storage_gb=600.0)
        assert result["allowed"] is False
        assert result["current"] == 600.0
        assert result["limit"] == 500.0
        assert result["pct"] == 120.0

    async def test_storage_quota_no_limit(self, svc, repo):
        """check_storage_quota sem limite (CAMERA_ONLY)."""
        lic = License(
            tenant_id=TenantId(uuid.uuid4()),
            license_type=LicenseType.CAMERA_ONLY,
        )
        repo.get_active_by_tenant = AsyncMock(return_value=[lic])
        result = await svc.check_storage_quota("t1", current_storage_gb=1000.0)
        assert result["allowed"] is True
        assert result["limit"] is None
        assert result["pct"] is None

    async def test_ai_quota_within_limit(self, svc, repo):
        """check_ai_quota dentro do limite."""
        lics = [
            License(
                tenant_id=TenantId(uuid.uuid4()),
                license_type=LicenseType.CAMERA_ANALYTICS,
                analytics_enabled=True,
            ),
            License(
                tenant_id=TenantId(uuid.uuid4()),
                license_type=LicenseType.CAMERA_ANALYTICS,
                analytics_enabled=True,
            ),
        ]
        repo.get_active_by_tenant = AsyncMock(return_value=lics)
        result = await svc.check_ai_quota("t1")
        # CAMERA_ANALYTICS tem max_ai_cameras = None (ilimitado)
        assert result["allowed"] is True
        assert result["current"] == 2
        assert result["limit"] is None

    async def test_ai_quota_no_analytics_licenses(self, svc, repo):
        """check_ai_quota sem licenças analytics."""
        lics = [
            License(
                tenant_id=TenantId(uuid.uuid4()),
                license_type=LicenseType.CAMERA_ONLY,
            ),
        ]
        repo.get_active_by_tenant = AsyncMock(return_value=lics)
        result = await svc.check_ai_quota("t1")
        assert result["allowed"] is True
        assert result["current"] == 0
        assert result["limit"] is None


class TestDefaultQuotas:
    """Testes das quotas padrão."""

    def test_camera_only_quotas(self):
        """Quotas para CAMERA_ONLY."""
        q = DEFAULT_QUOTAS[LicenseType.CAMERA_ONLY]
        assert q["max_cameras"] is None
        assert q["max_storage_gb"] is None
        assert q["max_ai_cameras"] == 0

    def test_camera_storage_quotas(self):
        """Quotas para CAMERA_STORAGE."""
        q = DEFAULT_QUOTAS[LicenseType.CAMERA_STORAGE]
        assert q["max_storage_gb"] == 500
        assert q["max_ai_cameras"] == 0

    def test_camera_analytics_quotas(self):
        """Quotas para CAMERA_ANALYTICS."""
        q = DEFAULT_QUOTAS[LicenseType.CAMERA_ANALYTICS]
        assert q["max_storage_gb"] == 1000
        assert q["max_ai_cameras"] is None  # ilimitado
        assert q["max_events_per_day"] == 10000


class TestQuotaExceededError:
    """Testes da exceção de quota."""

    def test_quota_exceeded_message(self):
        """Mensagem de erro formatada corretamente."""
        exc = QuotaExceededError("storage_gb", 600.0, 500.0)
        assert "storage_gb=600.0" in str(exc)
        assert "limite=500.0" in str(exc)
        assert exc.metric == "storage_gb"
        assert exc.current == 600.0
        assert exc.limit == 500.0
