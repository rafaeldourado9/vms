"""Entidades de domínio de faturamento e licenças."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from vms.shared.events import DomainEvent
from vms.shared.kernel import AuditId, BillingId, EntityId, TenantId


@dataclass(frozen=True)
class QuotaExceeded(DomainEvent):
    """Evento: tenant excedeu limite de quota."""
    tenant_id: TenantId | None = None
    metric_name: str = ""
    used: float = 0
    limit: float = 0
    severity: str = "warning"  # warning (80%) ou critical (100%)


@dataclass
class BillingPlan:
    """Plano de assinatura com limites e recursos."""

    id: BillingId
    name: str
    slug: str
    description: str | None = None
    price_monthly: float = 0.0
    max_cameras: int | None = None
    storage_limit_gb: int | None = None
    max_events_per_month: int | None = None
    max_retention_days: int = 7
    analytics_enabled: bool = True
    features: dict = field(default_factory=dict)
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Subscription:
    """Vínculo entre tenant e plano de assinatura."""

    tenant_id: TenantId
    plan_id: BillingId
    status: str = "active"  # active, cancelled, expired
    started_at: datetime | None = None
    expires_at: datetime | None = None


@dataclass
class UsageRecord:
    """Registro de consumo de um recurso por tenant."""

    id: BillingId
    tenant_id: TenantId
    metric_name: str
    value: float
    unit: str | None = None
    period_start: datetime = field(default_factory=datetime.utcnow)
    period_end: datetime = field(default_factory=datetime.utcnow)
    recorded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuotaStatus:
    """Status atual de uma métrica de quota."""

    metric_name: str
    used: float
    limit: float | None  # None = ilimitado
    unit: str = ""

    @property
    def is_unlimited(self) -> bool:
        return self.limit is None

    @property
    def usage_pct(self) -> float | None:
        if self.is_unlimited or self.limit == 0:
            return None
        return (self.used / self.limit) * 100

    @property
    def is_warning(self) -> bool:
        pct = self.usage_pct
        return pct is not None and 80 <= pct < 100

    @property
    def is_exceeded(self) -> bool:
        if self.is_unlimited:
            return False
        return self.used >= self.limit
