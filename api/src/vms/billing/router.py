"""Rotas HTTP para licenciamento por câmera."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from vms.billing.domain import LicenseType
from vms.billing.repository import LicenseRepository
from vms.billing.service import LicenseService
from vms.core.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/licenses", tags=["licenses"])


def _license_svc(db: DbSession) -> LicenseService:
    return LicenseService(LicenseRepository(db))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Criar licença para câmera",
)
async def create_license(
    claims: CurrentUser,
    db: DbSession,
    camera_id: str | None = Query(default=None),
    license_type: LicenseType = Query(default=LicenseType.CAMERA_ONLY),
    duration_days: int = Query(default=365, ge=30, le=3650),
    storage_limit_gb: int | None = Query(default=None),
    analytics_enabled: bool = Query(default=False),
) -> dict:
    """
    Cria nova licença para câmera.

    - CAMERA_ONLY: só gravação/streaming
    - CAMERA_STORAGE: câmera + storage adicional
    - CAMERA_ANALYTICS: câmera + storage + IA/analytics
    """
    svc = _license_svc(db)

    license = await svc.create_license(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        license_type=license_type,
        duration_days=duration_days,
        storage_limit_gb=storage_limit_gb,
        analytics_enabled=analytics_enabled,
    )

    await db.commit()

    return {
        "id": str(license.id),
        "camera_id": license.camera_id,
        "license_type": license.license_type,
        "status": license.status,
        "expires_at": license.expires_at.isoformat() if license.expires_at else None,
        "has_analytics": license.has_analytics,
        "storage_limit_gb": license.storage_limit_gb,
    }


@router.get(
    "/cameras/{camera_id}/validate",
    summary="Validar licença de câmera",
)
async def validate_camera_license(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Verifica se câmera tem licença ativa."""
    svc = _license_svc(db)
    validation = await svc.validate_camera(camera_id, claims.tenant_id)

    return {
        "is_valid": validation.is_valid,
        "camera_id": camera_id,
        "license_type": validation.license.license_type if validation.license else None,
        "expires_at": validation.license.expires_at.isoformat() if validation.license and validation.license.expires_at else None,
        "reason": validation.reason if not validation.is_valid else None,
    }


@router.get(
    "",
    summary="Listar licenças do tenant",
)
async def list_licenses(
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Retorna resumo de licenças ativas do tenant."""
    svc = _license_svc(db)
    return await svc.get_tenant_license_summary(claims.tenant_id)


@router.get(
    "/cameras/{camera_id}/analytics-allowed",
    summary="Verificar se analytics é permitido",
)
async def check_analytics_allowed(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Verifica se câmera tem licença que permite analytics."""
    svc = _license_svc(db)
    allowed = await svc.check_analytics_allowed(camera_id, claims.tenant_id)

    return {
        "camera_id": camera_id,
        "analytics_allowed": allowed,
    }
