"""Licença de ativação do VMS — sistema whitelabel.

Não é SaaS. Cada cliente tem UMA licença (serial key) que ativa a instalação.
A licença pode ser validada online ou offline (com grace period).
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class LicenseStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    TRIAL = "trial"


@dataclass
class VmsLicense:
    """Licença de ativação do VMS."""

    license_key: str              # Serial: VMS-XXXX-XXXX-XXXX-XXXX
    tenant_id: str
    status: LicenseStatus = LicenseStatus.ACTIVE
    max_cameras: int = 0          # 0 = ilimitado
    max_ai_cameras: int = 0       # 0 = sem IA
    expires_at: datetime | None = None
    activated_at: datetime | None = None
    hardware_id: str | None = None   # fingerprint da máquina
    customer_name: str = ""
    customer_email: str = ""

    @property
    def is_valid(self) -> bool:
        if self.status in (LicenseStatus.EXPIRED, LicenseStatus.REVOKED):
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    @classmethod
    def generate_key(cls) -> str:
        """Gera uma license key no formato VMS-XXXX-XXXX-XXXX-XXXX."""
        raw = uuid.uuid4().hex[:16].upper()
        parts = [raw[i:i+4] for i in range(0, 16, 4)]
        return f"VMS-{'-'.join(parts)}"

    @classmethod
    def verify_key_format(cls, key: str) -> bool:
        """Verifica se a key tem o formato válido."""
        import re
        return bool(re.match(r'^VMS-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$', key))

    def fingerprint(self) -> str:
        """Hash único da licença para verificação de integridade."""
        raw = f"{self.license_key}:{self.tenant_id}:{self.hardware_id}:{self.customer_email}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
