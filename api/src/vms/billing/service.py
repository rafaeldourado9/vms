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
