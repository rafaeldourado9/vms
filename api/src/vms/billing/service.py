"""Serviço de faturamento e validação de quotas."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from vms.billing.domain import BillingPlan, QuotaExceeded, QuotaStatus, UsageRecord
from vms.billing.repository import BillingRepository, BillingRepositoryPort
from vms.shared.events import DomainEvent

logger = logging.getLogger(__name__)


class QuotaChecker:
    """Verifica limites de quota para um tenant."""

    def __init__(self, plan: BillingPlan, current_usage: dict[str, float]) -> None:
        self._plan = plan
        self._usage = current_usage

    def check_camera_quota(self) -> QuotaStatus:
        """Verifica limite de câmeras."""
        used = self._usage.get("cameras", 0)
        return QuotaStatus(
            metric_name="cameras",
            used=used,
            limit=self._plan.max_cameras,
        )

    def check_storage_quota(self) -> QuotaStatus:
        """Verifica limite de armazenamento."""
        used_bytes = self._usage.get("storage_bytes", 0)
        limit_bytes = self._plan.storage_limit_gb * 1_000_000_000 if self._plan.storage_limit_gb else None
        return QuotaStatus(
            metric_name="storage",
            used=used_bytes,
            limit=limit_bytes,
            unit="bytes",
        )

    def check_events_quota(self) -> QuotaStatus:
        """Verifica limite de eventos mensais."""
        used = self._usage.get("events_month", 0)
        return QuotaStatus(
            metric_name="events_month",
            used=used,
            limit=self._plan.max_events_per_month,
        )

    def check_all_quotas(self) -> list[QuotaStatus]:
        """Verifica todas as quotas e retorna status."""
        return [
            self.check_camera_quota(),
            self.check_storage_quota(),
            self.check_events_quota(),
        ]

    def can_create_camera(self) -> bool:
        """Verifica se pode criar nova câmera."""
        status = self.check_camera_quota()
        return status.is_unlimited or not status.is_exceeded

    def can_record(self) -> bool:
        """Verifica se pode gravar (storage disponível)."""
        status = self.check_storage_quota()
        return status.is_unlimited or not status.is_exceeded


class BillingService:
    """Orquestra faturamento e quotas."""

    def __init__(self, repo: BillingRepositoryPort) -> None:
        self._repo = repo

    async def get_plan(self, slug: str) -> BillingPlan | None:
        return await self._repo.get_plan_by_slug(slug)

    async def list_plans(self) -> list[BillingPlan]:
        return await self._repo.list_active_plans()

    async def record_daily_usage(self, tenant_id: str, usage: dict[str, float]) -> None:
        """Registra uso diário do tenant."""
        now = datetime.now(timezone.utc)
        period_end = now.replace(hour=23, minute=59, second=59)
        period_start = now.replace(hour=0, minute=0, second=0)

        for metric, value in usage.items():
            record = UsageRecord(
                id=uuid4(),
                tenant_id=tenant_id,
                metric_name=metric,
                value=value,
                period_start=period_start,
                period_end=period_end,
            )
            await self._repo.record_usage(record)

    def create_checker(self, plan: BillingPlan, current_usage: dict[str, float]) -> QuotaChecker:
        return QuotaChecker(plan, current_usage)
