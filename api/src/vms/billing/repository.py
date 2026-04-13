"""Repositório SQLAlchemy para faturamento."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.billing.domain import BillingPlan, QuotaStatus, UsageRecord
from vms.billing.models import BillingPlanModel, UsageRecordModel


class BillingRepositoryPort(Protocol):
    """Interface do repositório de faturamento."""

    async def get_plan_by_slug(self, slug: str) -> BillingPlan | None: ...
    async def list_active_plans(self) -> list[BillingPlan]: ...
    async def record_usage(self, record: UsageRecord) -> UsageRecord: ...
    async def get_current_usage(self, tenant_id: str) -> dict[str, float]: ...


def _plan_to_domain(model: BillingPlanModel) -> BillingPlan:
    return BillingPlan(
        id=model.id,
        name=model.name,
        slug=model.slug,
        description=model.description,
        price_monthly=float(model.price_monthly or 0),
        max_cameras=model.max_cameras,
        storage_limit_gb=model.storage_limit_gb,
        max_events_per_month=model.max_events_per_month,
        max_retention_days=model.max_retention_days or 7,
        analytics_enabled=model.analytics_enabled if model.analytics_enabled is not None else True,
        features=model.features or {},
        is_active=model.is_active if model.is_active is not None else True,
        created_at=model.created_at or datetime.utcnow(),
    )


def _usage_to_domain(model: UsageRecordModel) -> UsageRecord:
    return UsageRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        metric_name=model.metric_name,
        value=float(model.value or 0),
        unit=model.unit,
        period_start=model.period_start,
        period_end=model.period_end,
        recorded_at=model.recorded_at or datetime.utcnow(),
    )


class BillingRepository:
    """Repositório SQLAlchemy para Billing."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_plan_by_slug(self, slug: str) -> BillingPlan | None:
        stmt = select(BillingPlanModel).where(
            BillingPlanModel.slug == slug,
            BillingPlanModel.is_active.is_(True),
        )
        model = await self._session.scalar(stmt)
        return _plan_to_domain(model) if model else None

    async def list_active_plans(self) -> list[BillingPlan]:
        stmt = select(BillingPlanModel).where(
            BillingPlanModel.is_active.is_(True),
        ).order_by(BillingPlanModel.price_monthly)
        result = await self._session.scalars(stmt)
        return [_plan_to_domain(m) for m in result.all()]

    async def record_usage(self, record: UsageRecord) -> UsageRecord:
        model = UsageRecordModel(
            id=record.id if hasattr(record, 'id') else record.id,
            tenant_id=record.tenant_id,
            metric_name=record.metric_name,
            value=record.value,
            unit=record.unit,
            period_start=record.period_start,
            period_end=record.period_end,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _usage_to_domain(model)

    async def get_current_usage(self, tenant_id: str) -> dict[str, float]:
        """Retorna contagens atuais do tenant."""
        from vms.cameras.models import CameraModel
        from vms.events.models import VmsEventModel
        from vms.recordings.models import RecordingSegmentModel
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Câmeras ativas
        cameras_stmt = select(func.count()).select_from(CameraModel).where(
            CameraModel.tenant_id == tenant_id,
            CameraModel.is_active.is_(True),
        )
        cameras = await self._session.scalar(cameras_stmt) or 0

        # Storage usado
        storage_stmt = select(func.coalesce(func.sum(RecordingSegmentModel.size_bytes), 0)).where(
            RecordingSegmentModel.tenant_id == tenant_id,
        )
        storage = await self._session.scalar(storage_stmt) or 0

        # Eventos do mês
        events_stmt = select(func.count()).select_from(VmsEventModel).where(
            VmsEventModel.tenant_id == tenant_id,
            VmsEventModel.occurred_at >= month_start,
        )
        events = await self._session.scalar(events_stmt) or 0

        return {
            "cameras": float(cameras),
            "storage_bytes": float(storage),
            "events_month": float(events),
        }
