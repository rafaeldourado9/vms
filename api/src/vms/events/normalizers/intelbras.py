"""Normalizador de payload ALPR para câmeras Intelbras ITSCAM."""
from __future__ import annotations

from datetime import datetime

from vms.events.domain import AlprDetection
from vms.events.normalizers.base import registry


class IntelbrasNormalizer:
    """
    Normaliza payload ALPR da Intelbras ITSCAM para AlprDetection.

    Formato esperado:
    {
        "placa": "ABC1D23",
        "confianca": 0.92,
        "timestamp": "2026-03-30T12:34:56",
        "imagem": "..."
    }
    """

    manufacturer: str = "intelbras"

    def can_handle(self, raw: dict) -> bool:
        """Retorna True se o payload contiver a chave 'placa'."""
        return "placa" in raw

    def normalize(
        self, raw: dict, camera_id: str, tenant_id: str
    ) -> AlprDetection:
        """Extrai placa, confiança e timestamp do payload Intelbras."""
        plate = str(raw["placa"]).upper().strip()
        confidence = float(raw.get("confianca", 0.0))
        timestamp = _parse_intelbras_datetime(raw.get("timestamp", ""))
        image_b64 = raw.get("imagem")

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


def _parse_intelbras_datetime(value: str) -> datetime:
    """Converte string ISO 8601 para datetime. Usa utcnow() como fallback."""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


# Auto-registra ao importar
registry.register(IntelbrasNormalizer())
