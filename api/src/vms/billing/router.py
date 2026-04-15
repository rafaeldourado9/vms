"""Rotas HTTP — dois modelos de licença + analytics pay-per-use."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from vms.billing.domain import VmsLicense, LicenseStatus, DeploymentModel
from vms.billing.models import LicenseKeyModel, AnalyticsPricingModel
from vms.billing.repository import LicenseRepository
from vms.billing.service import LicenseService
from vms.shared.api.dependencies import CurrentUser, DbSession, AdminUser
from vms.iam.models import TenantModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ─── Preços Analytics ─────────────────────────────────────────────────────

@router.get(
    "/analytics-pricing",
    summary="Preços de analytics por plugin",
)
async def get_analytics_pricing(db: DbSession) -> dict:
    """Retorna preços de analytics (light e pro)."""
    stmt = select(AnalyticsPricingModel).where(AnalyticsPricingModel.is_active.is_(True))
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return {
        "pricing": [
            {
                "plugin": r.plugin_name,
                "tier": r.tier,
                "price_per_camera_per_day": float(r.price_per_camera_per_day),
                "description": r.description,
            }
            for r in rules
        ],
    }


# ─── Fatura do mês ────────────────────────────────────────────────────────

@router.get(
    "/invoice",
    summary="Fatura do mês atual",
)
async def get_invoice(claims: CurrentUser, db: DbSession) -> dict:
    """Retorna fatura: storage (managed) + analytics por câmera/plugin."""
    # Buscar licença do tenant
    tenant_stmt = select(TenantModel).where(TenantModel.id == claims.tenant_id)
    tenant = await db.scalar(tenant_stmt)
    if not tenant or not tenant.license_key_id:
        return {"total": 0, "note": "Nenhuma licença ativa"}

    key_stmt = select(LicenseKeyModel).where(LicenseKeyModel.id == tenant.license_key_id)
    key = await db.scalar(key_stmt)
    if not key:
        return {"total": 0}

    items = []

    # Storage: apenas managed — R$50/cam/mês
    if key.deployment_model == "managed":
        from vms.cameras.models import CameraModel
        cam_count = await db.scalar(
            select(func.count(CameraModel.id)).where(CameraModel.tenant_id == claims.tenant_id)
        ) or 0
        storage_cost = cam_count * 50.00
        items.append({
            "item": "Storage",
            "detail": f"{cam_count} câmeras × R$ 50,00/mês",
            "total": storage_cost,
        })

    # Analytics: por câmera/plugin ativo
    # (na prática viria de uma tabela de usage_records, simplificado aqui)
    analytics_stmt = select(
        AnalyticsPricingModel.plugin_name,
        AnalyticsPricingModel.price_per_camera_per_day,
    ).where(AnalyticsPricingModel.is_active.is_(True))
    analytics_result = await db.execute(analytics_stmt)

    # Simulação: assume que todas as câmeras usam todos os plugins ativos
    # (em produção: viria de analytics plugin installations por câmera)
    cameras_with_analytics = 0  # viria de uma query de analytics installations

    for row in analytics_result:
        plugin = row.plugin_name
        price_per_day = float(row.price_per_camera_per_day)
        if cameras_with_analytics > 0:
            monthly_cost = price_per_day * cameras_with_analytics * 30
            items.append({
                "item": f"Analytics: {plugin}",
                "detail": f"{cameras_with_analytics} câmeras × R$ {price_per_day:.2f}/dia × 30 dias",
                "total": monthly_cost,
            })

    total = sum(i["total"] for i in items)

    return {
        "deployment_model": key.deployment_model,
        "license_key": key.license_key[:5] + "..." + key.license_key[-5:],
        "line_items": items,
        "total": round(total, 2),
        "currency": "BRL",
        "note": "Storage: por conta do cliente" if key.deployment_model == "self_hosted" else "Storage: incluso (R$50/cam/mês)",
    }


# ─── Ativação ─────────────────────────────────────────────────────────────

@router.post(
    "/activate",
    summary="Ativar licença",
)
async def activate_license(body: dict, claims: CurrentUser, db: DbSession) -> dict:
    """Ativa conta com license key."""
    license_key_str = body.get("license_key", "").strip().upper()

    if not VmsLicense.verify_key_format(license_key_str):
        raise HTTPException(status_code=400, detail="Formato inválido: XXXX-XXXXX-XXXXX-XXXXX-XXXXX")

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

    if key_model.tenant_id:
        return {
            "success": True,
            "message": "Licença já ativada",
            "deployment_model": key_model.deployment_model,
            "license_key": license_key_str,
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

    # Criar licenças de câmera iniciais
    license_svc = LicenseService(LicenseRepository(db))
    initial = key_model.max_cameras if key_model.max_cameras > 0 else 5
    for _ in range(initial):
        from vms.billing.domain import LicenseType
        await license_svc.create_license(
            tenant_id=claims.tenant_id,
            license_type=LicenseType.CAMERA_ONLY,
            duration_days=365,
        )

    await db.commit()

    logger.info("Tenant %s ativou %s: %s", claims.tenant_id, key_model.deployment_model, license_key_str)

    return {
        "success": True,
        "deployment_model": key_model.deployment_model,
        "license_key": license_key_str,
        "max_cameras": key_model.max_cameras,
        "expires_at": key_model.expires_at.isoformat() if key_model.expires_at else None,
        "licenses_created": initial,
        "onboarding_complete": True,
        "billing_note": (
            "Managed: R$ 15.000/ano + R$ 50/cam/mês storage + analytics mensal"
            if key_model.deployment_model == "managed"
            else "Self-Hosted: R$ 20.000/ano + storage/analytics por conta do cliente"
        ),
    }


@router.get("/status", summary="Status da licença")
async def get_license_status(claims: CurrentUser, db: DbSession) -> dict:
    tenant = await db.scalar(select(TenantModel).where(TenantModel.id == claims.tenant_id))
    if not tenant or not tenant.license_key_id:
        return {"active": False, "onboarding_complete": False}

    key = await db.scalar(select(LicenseKeyModel).where(LicenseKeyModel.id == tenant.license_key_id))
    if not key:
        return {"active": False}

    return {
        "active": True,
        "onboarding_complete": tenant.onboarding_complete,
        "deployment_model": key.deployment_model,
        "license_key": key.license_key[:5] + "..." + key.license_key[-5:],
        "max_cameras": key.max_cameras,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "status": key.status,
    }


# ─── Gerar License Key (Admin) ────────────────────────────────────────────

@router.post("/licenses/generate", status_code=status.HTTP_201_CREATED, summary="Gerar license key")
async def generate_license_key(body: dict, _claims: AdminUser, db: DbSession) -> dict:
    """Gera license key para cliente."""
    deployment_model = body.get("deployment_model", "managed")
    license_key = VmsLicense.generate_key()
    price = 15000.00 if deployment_model == "managed" else 20000.00

    model = LicenseKeyModel(
        license_key=license_key,
        deployment_model=deployment_model,
        max_cameras=body.get("max_cameras", 0),
        price_annual=price,
        status="active",
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    return {
        "license_key": license_key,
        "deployment_model": deployment_model,
        "max_cameras": model.max_cameras,
        "price_annual": price,
        "billing": (
            "Managed: R$ 15.000/ano + storage R$50/cam/mês + analytics mensal"
            if deployment_model == "managed"
            else "Self-Hosted: R$ 20.000/ano + storage/analytics por conta do cliente"
        ),
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
