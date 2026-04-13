"""Serviço de licenciamento — validação e gestão por câmera."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from vms.billing.domain import (
    License,
    LicenseCreated,
    LicenseExpired,
    LicenseStatus,
    LicenseType,
    LicenseValidation,
)
from vms.billing.repository import LicenseRepository, LicenseRepositoryPort
from vms.shared.kernel import BillingId, TenantId

logger = logging.getLogger(__name__)


# ─── Quotas padrão por tipo de licença ──────────────────────────────────────

DEFAULT_QUOTAS = {
    LicenseType.CAMERA_ONLY: {
        "max_cameras": None,       # ilimitado (controlado por licenças individuais)
        "max_storage_gb": None,
        "max_ai_cameras": 0,
        "max_events_per_day": None,
    },
    LicenseType.CAMERA_STORAGE: {
        "max_cameras": None,
        "max_storage_gb": 500,     # 500 GB por licença
        "max_ai_cameras": 0,
        "max_events_per_day": None,
    },
    LicenseType.CAMERA_ANALYTICS: {
        "max_cameras": None,
        "max_storage_gb": 1000,    # 1 TB por licença
        "max_ai_cameras": None,    # ilimitado (cada licença = 1 câmera AI)
        "max_events_per_day": 10000,
    },
}


class QuotaExceededError(Exception):
    """Exceção levantada quando quota é excedida."""
    def __init__(self, metric: str, current: int | float, limit: int | float) -> None:
        self.metric = metric
        self.current = current
        self.limit = limit
        super().__init__(f"Quota excedida: {metric}={current}, limite={limit}")


class LicenseService:
    """Orquestra licenciamento por câmera."""

    def __init__(self, repo: LicenseRepositoryPort) -> None:
        self._repo = repo

    async def create_license(
        self,
        tenant_id: str,
        camera_id: str | None = None,
        license_type: LicenseType = LicenseType.CAMERA_ONLY,
        duration_days: int = 365,
        storage_limit_gb: int | None = None,
        analytics_enabled: bool = False,
    ) -> License:
        """
        Cria nova licença para câmera.

        Args:
            tenant_id: ID do tenant
            camera_id: ID da câmera (None = licença avulsa para ativar depois)
            license_type: Tipo de licença
            duration_days: Validade em dias (default: 1 ano)
            storage_limit_gb: Limite de storage extra (para CAMERA_STORAGE/ANALYTICS)
            analytics_enabled: Habilitar analytics (para CAMERA_ANALYTICS)
        """
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        license = License(
            id=BillingId(uuid4()),
            tenant_id=TenantId(tenant_id),
            camera_id=camera_id,
            license_type=license_type,
            storage_limit_gb=storage_limit_gb if license_type != LicenseType.CAMERA_ONLY else None,
            analytics_enabled=analytics_enabled if license_type == LicenseType.CAMERA_ANALYTICS else False,
            expires_at=expires_at,
        )

        created = await self._repo.create(license)

        # Registrar evento de domínio
        created.record_event(LicenseCreated(
            license_id=created.id,
            tenant_id=created.tenant_id,
            camera_id=created.camera_id,
            license_type=created.license_type,
        ))

        logger.info(
            "Licença criada: type=%s camera=%s tenant=%s expires=%s",
            license_type,
            camera_id,
            tenant_id,
            expires_at.isoformat(),
        )

        return created

    async def validate_camera(self, camera_id: str, tenant_id: str) -> LicenseValidation:
        """Valida se câmera tem licença ativa."""
        return await self._repo.validate_camera(camera_id, tenant_id)

    async def check_analytics_allowed(self, camera_id: str, tenant_id: str) -> bool:
        """Verifica se câmera pode usar analytics."""
        validation = await self.validate_camera(camera_id, tenant_id)
        if not validation.is_valid:
            return False
        return validation.license.has_analytics if validation.license else False

    async def get_tenant_license_summary(self, tenant_id: str) -> dict:
        """Retorna resumo de licenças do tenant."""
        licenses = await self._repo.get_active_by_tenant(tenant_id)
        count = await self._repo.count_active_by_tenant(tenant_id)

        by_type = {}
        for lic in licenses:
            t = lic.license_type
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total_active": count,
            "by_type": by_type,
            "licenses": [
                {
                    "id": str(l.id),
                    "camera_id": l.camera_id,
                    "type": l.license_type,
                    "status": l.status,
                    "expires_at": l.expires_at.isoformat() if l.expires_at else None,
                    "has_analytics": l.has_analytics,
                    "storage_gb": l.storage_limit_gb,
                }
                for l in licenses
            ],
        }

    # ─── Quota Checks ──────────────────────────────────────────────────────

    async def check_camera_quota(self, tenant_id: str, db_session=None) -> dict:
        """
        Verifica se tenant pode adicionar mais câmeras.

        Retorna: {allowed: bool, current: int, limit: int|None, pct: float|None}
        """
        current = await self._repo.count_active_by_tenant(tenant_id)
        # Limite = número de licenças CAMERA_* ativas (cada licença = 1 câmera)
        limit = current  # Se já tem licenças, pode usar; senão, 0
        allowed = limit > 0 or limit is None

        pct = (current / limit * 100) if limit else None

        return {
            "allowed": allowed,
            "current": current,
            "limit": limit,
            "pct": pct,
        }

    async def check_storage_quota(self, tenant_id: str, current_storage_gb: float) -> dict:
        """
        Verifica quota de storage do tenant.

        Args:
            tenant_id: ID do tenant
            current_storage_gb: Uso atual em GB

        Retorna: {allowed: bool, current: float, limit: float|None, pct: float|None}
        """
        licenses = await self._repo.get_active_by_tenant(tenant_id)
        total_limit_gb = 0.0
        has_limit = False

        for lic in licenses:
            quotas = DEFAULT_QUOTAS.get(lic.license_type, {})
            lic_limit = quotas.get("max_storage_gb")
            if lic_limit is not None:
                total_limit_gb += lic_limit
                has_limit = True

        if not has_limit:
            return {"allowed": True, "current": current_storage_gb, "limit": None, "pct": None}

        pct = (current_storage_gb / total_limit_gb * 100) if total_limit_gb > 0 else 0
        allowed = current_storage_gb < total_limit_gb

        return {
            "allowed": allowed,
            "current": round(current_storage_gb, 2),
            "limit": round(total_limit_gb, 2),
            "pct": round(pct, 1),
        }

    async def check_ai_quota(self, tenant_id: str) -> dict:
        """
        Verifica quota de câmeras com IA.

        Retorna: {allowed: bool, current: int, limit: int|None, pct: float|None}
        """
        licenses = await self._repo.get_active_by_tenant(tenant_id)
        ai_count = sum(1 for l in licenses if l.license_type == LicenseType.CAMERA_ANALYTICS)
        total = len(licenses)

        quotas = DEFAULT_QUOTAS.get(LicenseType.CAMERA_ANALYTICS, {})
        limit = quotas.get("max_ai_cameras")

        if limit is None:
            return {"allowed": True, "current": ai_count, "limit": None, "pct": None}

        pct = (ai_count / limit * 100) if limit > 0 else 0
        allowed = ai_count < limit

        return {
            "allowed": allowed,
            "current": ai_count,
            "limit": limit,
            "pct": round(pct, 1),
        }
