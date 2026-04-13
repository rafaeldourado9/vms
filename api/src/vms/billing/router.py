"""Rotas HTTP para billing — licença anual + storage + analytics pay-per-use."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func as sa_func

from vms.billing.domain import VmsLicense, LicenseStatus
from vms.billing.models import LicenseKeyModel, PricingRuleModel, UsageRecordModel
from vms.billing.repository import LicenseRepository
from vms.billing.service import LicenseService
from vms.core.deps import CurrentUser, DbSession, AdminUser
from vms.iam.models import TenantModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ─── Preços (Pricing Rules) ────────────────────────────────────────────────

@router.get(
    "/pricing",
    summary="Tabela de preços (storage + analytics)",
)
async def get_pricing(db: DbSession) -> dict:
    """Retorna preços atuais. Não requer auth."""
    stmt = select(PricingRuleModel).where(PricingRuleModel.is_active.is_(True))
    result = await db.execute(stmt)
    rules = result.scalars().all()

    return {
        "pricing": [
            {
                "usage_type": r.usage_type,
                "unit": r.unit,
                "price_per_unit": float(r.price_per_unit),
                "description": r.description,
            }
            for r in rules
        ],
    }


# ─── Fatura do mês atual ──────────────────────────────────────────────────

@router.get(
    "/invoice",
    summary="Fatura do mês atual",
)
async def get_invoice(claims: CurrentUser, db: DbSession) -> dict:
    """Retorna fatura do mês: storage + analytics usados."""
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # Storage usado
    storage_stmt = sa_func.sum(UsageRecordModel.total_price).where(
        UsageRecordModel.tenant_id == claims.tenant_id,
        UsageRecordModel.usage_type == "storage",
        UsageRecordModel.period_start >= period_start,
        UsageRecordModel.period_end <= period_end,
    )
    storage_total = await db.scalar(storage_stmt) or 0

    # Analytics: agrupar por plugin
    analytics_stmt = select(
        UsageRecordModel.usage_type,
        sa_func.count(UsageRecordModel.camera_id).label("cameras"),
        sa_func.sum(UsageRecordModel.total_price).label("total"),
    ).where(
        UsageRecordModel.tenant_id == claims.tenant_id,
        UsageRecordModel.usage_type != "storage",
        UsageRecordModel.period_start >= period_start,
        UsageRecordModel.period_end <= period_end,
    ).group_by(UsageRecordModel.usage_type)
    analytics_result = await db.execute(analytics_stmt)
    analytics_rows = analytics_result.all()

    analytics_total = sum(float(r.total) for r in analytics_rows)
    total = float(storage_total) + analytics_total

    return {
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
        },
        "storage": {
            "total": float(storage_total),
            "unit": "R$/mês",
        },
        "analytics": [
            {
                "plugin": r.usage_type,
                "cameras_using": r.cameras,
                "total": float(r.total),
            }
            for r in analytics_rows
        ],
        "total": round(total, 2),
        "currency": "BRL",
    }


# ─── Ativação de Licença ──────────────────────────────────────────────────

@router.post(
    "/activate",
    summary="Ativar licença com license key",
)
async def activate_license(
    body: dict,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Ativa a conta do tenant usando uma license key anual."""
    license_key_str = body.get("license_key", "").strip().upper()

    if not VmsLicense.verify_key_format(license_key_str):
        raise HTTPException(status_code=400, detail="Formato inválido: VMS-XXXX-XXXX-XXXX-XXXX")

    stmt = select(LicenseKeyModel).where(LicenseKeyModel.license_key == license_key_str)
    key_model = await db.scalar(stmt)

    if not key_model:
        raise HTTPException(status_code=404, detail="License key não encontrada")
    if key_model.status == LicenseStatus.REVOKED:
        raise HTTPException(status_code=403, detail="Licença revogada")
    if key_model.status == LicenseStatus.EXPIRED:
        raise HTTPException(status_code=403, detail="Licença expirada")
    if key_model.tenant_id and str(key_model.tenant_id) != claims.tenant_id:
        raise HTTPException(status_code=409, detail="Licença já ativada por outro tenant")

    # Idempotente
    if key_model.tenant_id and str(key_model.tenant_id) == claims.tenant_id:
        return {
            "success": True,
            "message": "Licença já ativada",
            "license_key": license_key_str,
            "max_cameras": key_model.max_cameras,
            "expires_at": key_model.expires_at.isoformat() if key_model.expires_at else None,
        }

    # Ativar
    key_model.tenant_id = claims.tenant_id
    key_model.activated_at = datetime.now(timezone.utc)

    tenant_stmt = select(TenantModel).where(TenantModel.id == claims.tenant_id)
    tenant = await db.scalar(tenant_stmt)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    tenant.onboarding_complete = True
    tenant.license_key_id = key_model.id
    tenant.subscription_status = "active"
    tenant.subscription_started_at = datetime.now(timezone.utc)

    # Criar licenças de câmera iniciais
    license_svc = LicenseService(LicenseRepository(db))
    initial_licenses = key_model.max_cameras if key_model.max_cameras > 0 else 5
    for _ in range(initial_licenses):
        from vms.billing.domain import LicenseType
        await license_svc.create_license(
            tenant_id=claims.tenant_id,
            license_type=LicenseType.CAMERA_ONLY,
            duration_days=365,
        )

    await db.commit()

    logger.info("Tenant %s ativou licença %s", claims.tenant_id, license_key_str)

    return {
        "success": True,
        "license_key": license_key_str,
        "max_cameras": key_model.max_cameras,
        "expires_at": key_model.expires_at.isoformat() if key_model.expires_at else None,
        "licenses_created": initial_licenses,
        "onboarding_complete": True,
    }


@router.get(
    "/status",
    summary="Status da licença do tenant",
)
async def get_license_status(claims: CurrentUser, db: DbSession) -> dict:
    """Status da licença do tenant."""
    stmt = select(TenantModel).where(TenantModel.id == claims.tenant_id)
    tenant = await db.scalar(stmt)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")

    if not tenant.license_key_id:
        return {"active": False, "onboarding_complete": False, "message": "Nenhuma licença ativada"}

    key_stmt = select(LicenseKeyModel).where(LicenseKeyModel.id == tenant.license_key_id)
    key = await db.scalar(key_stmt)
    if not key:
        return {"active": False, "message": "Licença não encontrada"}

    return {
        "active": True,
        "onboarding_complete": tenant.onboarding_complete,
        "license_key": key.license_key[:8] + "..." + key.license_key[-4:],
        "max_cameras": key.max_cameras,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "status": key.status,
        "usage": {"cameras": tenant.current_usage_cameras},
    }


# ─── Gerar License Key (Admin Global) ─────────────────────────────────────

@router.post(
    "/licenses/generate",
    status_code=status.HTTP_201_CREATED,
    summary="Gerar license key (admin global)",
)
async def generate_license_key(body: dict, _claims: AdminUser, db: DbSession) -> dict:
    """Gera license key anual para cliente."""
    license_key = VmsLicense.generate_key()

    model = LicenseKeyModel(
        license_key=license_key,
        max_cameras=body.get("max_cameras", 0),
        price_annual=body.get("price_annual", 0),
        status="active",
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    return {
        "license_key": license_key,
        "max_cameras": model.max_cameras,
        "price_annual": float(model.price_annual),
        "note": "Envie esta key ao cliente. Válida por 1 ano após ativação.",
    }


# ─── Licenças de Câmera (interno) ─────────────────────────────────────────

from vms.billing.domain import LicenseType as LicenseTypeEnum
from vms.billing.service import LicenseService as LicenseSvc

license_router = APIRouter(prefix="/licenses", tags=["licenses"])


def _license_svc(db: DbSession) -> LicenseSvc:
    return LicenseSvc(LicenseRepository(db))


@license_router.post("", status_code=status.HTTP_201_CREATED, summary="Criar licença para câmera")
async def create_license(
    claims: CurrentUser, db: DbSession,
    camera_id: str | None = Query(default=None),
    license_type: LicenseTypeEnum = Query(default=LicenseTypeEnum.CAMERA_ONLY),
    duration_days: int = Query(default=365, ge=30, le=3650),
) -> dict:
    svc = _license_svc(db)
    lic = await svc.create_license(tenant_id=claims.tenant_id, camera_id=camera_id, license_type=license_type, duration_days=duration_days)
    await db.commit()
    return {"id": str(lic.id), "camera_id": lic.camera_id, "license_type": lic.license_type, "status": lic.status}


@license_router.get("", summary="Listar licenças do tenant")
async def list_licenses(claims: CurrentUser, db: DbSession) -> dict:
    return await _license_svc(db).get_tenant_license_summary(claims.tenant_id)
