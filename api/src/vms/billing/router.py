"""Rotas HTTP para faturamento e licenças."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.billing.domain import BillingPlan, QuotaStatus
from vms.billing.repository import BillingRepository
from vms.billing.service import BillingService, QuotaChecker
from vms.cameras.models import CameraModel
from vms.core.deps import CurrentUser, DbSession
from vms.iam.models import TenantModel
from vms.events.models import VmsEventModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _billing_svc(db: DbSession) -> BillingService:
    return BillingService(BillingRepository(db))


@router.get(
    "/plans",
    summary="Listar planos disponíveis",
)
async def list_plans(db: DbSession) -> list[dict]:
    """Retorna planos de assinatura ativos."""
    svc = _billing_svc(db)
    plans = await svc.list_plans()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "price_monthly": p.price_monthly,
            "max_cameras": p.max_cameras,
            "storage_limit_gb": p.storage_limit_gb,
            "max_events_per_month": p.max_events_per_month,
            "max_retention_days": p.max_retention_days,
            "analytics_enabled": p.analytics_enabled,
            "features": p.features,
        }
        for p in plans
    ]


@router.get(
    "/usage",
    summary="Uso atual do tenant",
)
async def get_usage(
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Retorna métricas de uso atual do tenant e status de quotas."""
    repo = BillingRepository(db)
    usage = await repo.get_current_usage(claims.tenant_id)

    # Buscar plano do tenant
    tenant_stmt = select(TenantModel).where(TenantModel.id == claims.tenant_id)
    tenant = await db.scalar(tenant_stmt)

    plan = None
    quotas = []
    if tenant and tenant.billing_plan_id:
        svc = _billing_svc(db)
        plan_model = await db.get(BillingPlanModel, tenant.billing_plan_id)  # type: ignore
        if plan_model:
            from vms.billing.repository import _plan_to_domain
            plan = _plan_to_domain(plan_model)
            checker = QuotaChecker(plan, usage)
            quotas = checker.check_all_quotas()

    return {
        "tenant_id": claims.tenant_id,
        "current_usage": {
            "cameras": int(usage.get("cameras", 0)),
            "storage_bytes": int(usage.get("storage_bytes", 0)),
            "storage_gb": round(usage.get("storage_bytes", 0) / 1_000_000_000, 2),
            "events_this_month": int(usage.get("events_month", 0)),
        },
        "plan": {
            "id": str(plan.id),
            "name": plan.name,
            "slug": plan.slug,
            "max_cameras": plan.max_cameras,
            "storage_limit_gb": plan.storage_limit_gb,
        } if plan else None,
        "quotas": [
            {
                "metric": q.metric_name,
                "used": q.used,
                "limit": q.limit,
                "unit": q.unit,
                "usage_pct": q.usage_pct,
                "is_warning": q.is_warning,
                "is_exceeded": q.is_exceeded,
                "is_unlimited": q.is_unlimited,
            }
            for q in quotas
        ],
    }


@router.get(
    "/admin/dashboard",
    summary="Dashboard financeiro admin global",
)
async def admin_dashboard(db: DbSession) -> dict:
    """Visão global de faturamento e uso de todos os tenants."""
    # Tenants e suas câmeras
    tenant_stats = select(
        TenantModel.id,
        TenantModel.name,
        TenantModel.slug,
        TenantModel.billing_plan_id,
        func.count(CameraModel.id).label("camera_count"),
    ).outerjoin(
        CameraModel,
        (TenantModel.id == CameraModel.tenant_id) & (CameraModel.is_active.is_(True)),
    ).group_by(
        TenantModel.id, TenantModel.name, TenantModel.slug, TenantModel.billing_plan_id,
    )
    
    result = await db.execute(tenant_stats)
    rows = result.all()

    tenants = []
    total_cameras = 0
    for row in rows:
        camera_count = row.camera_count or 0
        total_cameras += camera_count
        tenants.append({
            "id": str(row.id),
            "name": row.name,
            "slug": row.slug,
            "camera_count": camera_count,
            "billing_plan_id": str(row.billing_plan_id) if row.billing_plan_id else None,
        })

    # Eventos totais
    events_stmt = select(func.count()).select_from(VmsEventModel)
    total_events = await db.scalar(events_stmt) or 0

    return {
        "tenants": tenants,
        "summary": {
            "total_tenants": len(tenants),
            "total_cameras": total_cameras,
            "total_events": total_events,
        },
    }


# Import BillingPlanModel para o admin_dashboard funcionar
from vms.billing.models import BillingPlanModel
