"""Entidades de domínio de faturamento — Licenciamento por recurso."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from vms.shared.events import DomainEvent
from vms.shared.kernel import AuditId, BillingId, EntityId, TenantId


class LicenseType(StrEnum):
    """Tipos de licença disponíveis."""

    CAMERA_ONLY = "camera_only"              # Só gravação/streaming
    CAMERA_STORAGE = "camera_storage"        # Câmera + storage adicional
    CAMERA_ANALYTICS = "camera_analytics"    # Câmera + storage + IA/analytics


class LicenseStatus(StrEnum):
    """Estado de uma licença."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class LicenseCreated(DomainEvent):
    """Evento: licença criada para câmera."""
    license_id: BillingId | None = None
    tenant_id: TenantId | None = None
    camera_id: str | None = None
    license_type: str = ""


@dataclass(frozen=True)
class LicenseExpired(DomainEvent):
    """Evento: licença expirou."""
    license_id: BillingId | None = None
    tenant_id: TenantId | None = None
    camera_id: str | None = None


@dataclass
class License:
    """
    Licença de uso por câmera.

    Modelo de negócio:
    - Cada câmera precisa de uma licença ativa para funcionar
    - CAMERA_ONLY: gravação e streaming básico
    - CAMERA_STORAGE: câmera + storage adicional configurável
    - CAMERA_ANALYTICS: câmera + storage + IA/analytics

    Sem licença ativa → câmera não grava, não faz analytics.
    """

    id: BillingId
    tenant_id: TenantId
    camera_id: str | None = None  # NULL = licença avulsa (para ativar depois)
    license_type: LicenseType = LicenseType.CAMERA_ONLY
    status: LicenseStatus = LicenseStatus.ACTIVE
    storage_limit_gb: int | None = None
    analytics_enabled: bool = False
    activated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        """Verifica se licença está ativo e não expirado. Auto-expira se necessário."""
        if self.status != LicenseStatus.ACTIVE:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False  # Chamador deve chamar expire_if_past() para persistir
        return True

    def expire_if_past(self) -> bool:
        """
        Verifica se expirou e atualiza status localmente.
        Retorna True se status foi alterado para EXPIRED.
        """
        if self.status == LicenseStatus.ACTIVE and self.expires_at and datetime.utcnow() > self.expires_at:
            self.status = LicenseStatus.EXPIRED
            self.record_event(LicenseExpired(
                license_id=self.id,
                tenant_id=self.tenant_id,
                camera_id=self.camera_id,
            ))
            return True
        return False

    @property
    def has_analytics(self) -> bool:
        """Verifica se inclui analytics."""
        return self.license_type == LicenseType.CAMERA_ANALYTICS and self.analytics_enabled

    @property
    def has_extra_storage(self) -> bool:
        """Verifica se inclui storage adicional."""
        return (
            self.license_type in (LicenseType.CAMERA_STORAGE, LicenseType.CAMERA_ANALYTICS)
            and self.storage_limit_gb is not None
        )


@dataclass
class LicenseValidation:
    """Resultado da validação de licença."""

    is_valid: bool
    license: License | None = None
    reason: str = ""

    @property
    def error_message(self) -> str:
        if self.is_valid:
            return ""
        return f"Licença inválida: {self.reason}"
