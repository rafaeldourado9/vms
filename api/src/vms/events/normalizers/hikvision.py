"""Normalizador de payload ALPR para câmeras Hikvision ANPR."""
from __future__ import annotations

from datetime import datetime

from vms.events.domain import AlprDetection
from vms.events.normalizers.base import registry


class HikvisionNormalizer:
    """
    Normaliza payload ANPR da Hikvision para AlprDetection.

    Formato esperado:
    {
        "ANPR": {"licensePlate": "ABC1D23", "confidence": 85},
        "dateTime": "20260330123456",
        "pictureBase64": "..."
    }
    """

    manufacturer: str = "hikvision"

    def can_handle(self, raw: dict) -> bool:
        """Retorna True se o payload contiver a chave 'ANPR'."""
        return "ANPR" in raw

    def normalize(
        self, raw: dict, camera_id: str, tenant_id: str
    ) -> AlprDetection:
        """Extrai placa, confiança e timestamp do payload Hikvision."""
        anpr = raw["ANPR"]
        plate = anpr["licensePlate"].upper().strip()
        confidence = float(anpr.get("confidence", 0)) / 100.0
        timestamp = _parse_hikvision_datetime(raw.get("dateTime", ""))
        image_b64 = raw.get("pictureBase64")

        return AlprDetection(
            camera_id=camera_id,
            tenant_id=tenant_id,
            plate=plate,
            confidence=confidence,
            manufacturer=self.manufacturer,
            timestamp=timestamp,
            raw_payload=raw,
            image_b64=image_b64,
        )


def _parse_hikvision_datetime(value: str) -> datetime:
    """Converte string 'YYYYMMDDHHmmss' para datetime. Usa utcnow() como fallback."""
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S")
    except (ValueError, TypeError):
        return datetime.utcnow()


# Auto-registra ao importar
registry.register(HikvisionNormalizer())
