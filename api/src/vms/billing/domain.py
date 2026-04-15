"""Licença de ativação do VMS — sistema whitelabel.

Dois modelos:
1. White Label (Managed) — R$ 15.000/ano + storage mensal (R$50/cam/mês) + analytics mensal
2. White Label (Self-Hosted) — R$ 20.000/ano + storage por conta do cliente + analytics por conta do cliente
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from vms.shared.events import DomainEvent
from vms.shared.kernel import AggregateRoot, BillingId, EntityId, TenantId


# ─── VMS License (Whitelabel activation) ──────────────────────────────────


class DeploymentModel(StrEnum):
    MANAGED = "managed"       # White Label — cuidamos da infra
    SELF_HOSTED = "self_hosted"  # White Label — cliente cuida da infra


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class LicenseType(StrEnum):
    """Tipo de licença por câmera."""
    CAMERA_ONLY = "camera_only"
    CAMERA_STORAGE = "camera_storage"
    CAMERA_ANALYTICS = "camera_analytics"


@dataclass
class VmsLicense:
    """Licença de ativação do VMS."""

    license_key: str              # Serial: VKMH-WXSAQ-XQQWR-CAMWQ-QDAFW
    deployment_model: DeploymentModel = DeploymentModel.MANAGED
    max_cameras: int = 0          # 0 = ilimitado
    status: LicenseStatus = LicenseStatus.ACTIVE
    expires_at: datetime | None = None
    activated_at: datetime | None = None
    hardware_id: str | None = None   # fingerprint da máquina (self-hosted)
    customer_name: str = ""
    customer_email: str = ""

    @property
    def is_valid(self) -> bool:
        if self.status in (LicenseStatus.EXPIRED, LicenseStatus.REVOKED):
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    @property
    def annual_price(self) -> float:
        """Preço da licença anual."""
        if self.deployment_model == DeploymentModel.MANAGED:
            return 15000.00
        return 20000.00

    @property
    def storage_monthly_per_camera(self) -> float | None:
        """Storage mensal por câmera (managed only)."""
        if self.deployment_model == DeploymentModel.MANAGED:
            return 50.00
        return None  # por conta do cliente

    @classmethod
    def generate_key(cls) -> str:
        """Gera license key no formato XXXX-XXXXX-XXXXX-XXXXX-XXXXX."""
        raw = uuid.uuid4().hex[:24].upper()
        # 4-5-5-5-5 format
        parts = [raw[:4], raw[4:9], raw[9:14], raw[14:19], raw[19:24]]
        return "-".join(parts)

    @classmethod
    def verify_key_format(cls, key: str) -> bool:
        """Verifica formato: XXXX-XXXXX-XXXXX-XXXXX-XXXXX."""
        import re
        return bool(re.match(r'^[A-Z0-9]{4}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}$', key))

    def fingerprint(self) -> str:
        """Hash único da licença."""
        raw = f"{self.license_key}:{self.deployment_model}:{self.hardware_id}:{self.customer_email}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ─── Camera License (per-camera licensing) ────────────────────────────────


@dataclass(frozen=True)
class LicenseCreated(DomainEvent):
    """Evento de domínio: licença criada."""
    license_id: BillingId | None = None
    tenant_id: TenantId | None = None
    camera_id: str | None = None
    license_type: LicenseType | None = None


@dataclass(frozen=True)
class LicenseExpired(DomainEvent):
    """Evento de domínio: licença expirou."""
    license_id: BillingId | None = None
    tenant_id: TenantId | None = None
    camera_id: str | None = None


@dataclass
class LicenseValidation:
    """Resultado da validação de uma licença."""
    is_valid: bool = False
    license: License | None = None
    reason: str = ""


@dataclass
class License(AggregateRoot):
    """
    Licença por câmera.

    Controla o acesso de cada câmera ao sistema.
    Tipos: CAMERA_ONLY, CAMERA_STORAGE, CAMERA_ANALYTICS.
    """
    id: BillingId = field(default_factory=lambda: BillingId(uuid.uuid4()))
    tenant_id: TenantId | None = None
    camera_id: str | None = None
    license_type: LicenseType = LicenseType.CAMERA_ONLY
    status: LicenseStatus = LicenseStatus.ACTIVE
    storage_limit_gb: int | None = None
    analytics_enabled: bool = False
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        """Licença está ativa e não expirada."""
        if self.status != LicenseStatus.ACTIVE:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    @property
    def has_analytics(self) -> bool:
        """Licença inclui analytics."""
        return self.license_type == LicenseType.CAMERA_ANALYTICS and self.analytics_enabled

    def expire(self) -> None:
        """Expira a licença."""
        self.status = LicenseStatus.EXPIRED
        self.record_event(LicenseExpired(
            license_id=self.id,
            tenant_id=self.tenant_id,
            camera_id=self.camera_id,
        ))
