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


class DeploymentModel(StrEnum):
    MANAGED = "managed"       # White Label — cuidamos da infra
    SELF_HOSTED = "self_hosted"  # White Label — cliente cuida da infra


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


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
