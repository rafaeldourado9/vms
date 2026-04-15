"""Normalizador de payload ALPR para câmeras Intelbras."""
from __future__ import annotations

import base64
import logging
import re
from datetime import datetime

from vms.events.domain import AlprDetection
from vms.events.normalizers.base import registry

logger = logging.getLogger(__name__)

# Strings que aparecem no JPEG Dahua ITC mas NÃO são placas
_ITSCAM_NON_PLATE_STRINGS = frozenset({
    "Desconhecido", "Car come in", "Car go out", "ANPR", "DHAV3a",
    "JFIF", "Unknown", "Unkonwn",  # typo comum no firmware Dahua
})


def _extract_itscam_plate(raw_bytes: bytes) -> str | None:
    """
    Extrai placa do JPEG Dahua ITC / Intelbras ITSCAM.

    O JPEG tem uma seção APP2 proprietária com estrutura:
      ... ANPR ... Car come in ... Car go out ... <PLACA> ... DHAV3a ...

    A placa aparece como string ASCII após o bloco ANPR+Car labels.
    Se a câmera não detectou placa, o campo contém "Desconhecido".
    """
    anpr_pos = raw_bytes.find(b'ANPR')
    if anpr_pos < 0:
        return None

    # A placa está entre ANPR+200 e ANPR+2500 (depois dos labels Car come in / Car go out)
    search_zone = raw_bytes[anpr_pos + 200: anpr_pos + 2500]
    strings = re.findall(rb'[\x20-\x7E]{4,}', search_zone)

    for s in strings:
        text = s.decode("ascii", errors="ignore").strip()
        if len(set(text)) <= 2:  # strings triviais como "....", "0000"
            continue
        if text in _ITSCAM_NON_PLATE_STRINGS:
            if text == "Desconhecido" or text.startswith("Unknown"):
                logger.debug("ITSCAM: placa não detectada no frame (%s)", text)
                return None  # Nenhuma placa no frame — evento irrelevante
            continue
        # Encontrou a placa
        logger.debug("ITSCAM: placa extraída do JPEG: %s", text)
        return text.upper()

    return None


class IntelbrasNormalizer:
    """
    Normaliza payloads ANPR/LPR da Intelbras para AlprDetection.

    Suporta múltiplos formatos conforme o modelo:

    Formato 1 — ITSCAM 450/460 (campos em português):
        {"placa": "ABC1234", "confianca": 0.92, "timestamp": "2026-04-11T10:58:07"}

    Formato 2 — Modelos novos (campos em inglês):
        {"plate": "ABC1234", "confidence": 92, "timestamp": "2026-04-11T10:58:07", "channel": 1}

    Formato 3 — DVR/NVR Intelbras (lista de eventos):
        {
            "ChannelID": 1,
            "DateTime": "2026-04-11T10:58:07",
            "Events": [{"EventType": "AnprEvent", "LicensePlate": "ABC1234", "Confidence": 92}]
        }

    Formato 4 — ITSCAM ANPR via /NotificationInfo/TollgateInfo (Dahua ITC firmware):
        {"Picture": {"NormalPic": {"Content": "<base64 JPEG com placa embutida>"}}}
    """

    manufacturer: str = "intelbras"

    def can_handle(self, raw: dict) -> bool:
        """Detecta payload Intelbras com leitura de placa."""
        # Formato 4: ITSCAM ANPR — JPEG com placa embutida no binário
        if raw.get("Picture", {}).get("NormalPic", {}).get("Content"):
            return True
        # Formato 1: campo 'placa' (PT)
        if "placa" in raw:
            return True
        # Formato 2: campo 'plate' APENAS se também tiver 'confianca' ou 'Events' (para não conflitar com generic)
        if "plate" in raw and ("confianca" in raw or "Events" in raw):
            return True
        # Formato 3: DVR/NVR com lista Events contendo AnprEvent
        events = raw.get("Events", [])
        if isinstance(events, list) and events:
            first = events[0] if isinstance(events[0], dict) else {}
            if "LicensePlate" in first or "Plate" in first or first.get("EventType") == "AnprEvent":
                return True
        return False

    def normalize(
        self, raw: dict, camera_id: str, tenant_id: str
    ) -> AlprDetection | None:
        """Extrai placa e confiança do payload Intelbras."""
        plate = ""
        confidence = 0.0
        timestamp = datetime.utcnow()
        image_b64 = None

        # Formato 4: ITSCAM ANPR — extrai placa do JPEG
        content = raw.get("Picture", {}).get("NormalPic", {}).get("Content", "")
        if content:
            image_b64 = content
            try:
                raw_bytes = base64.b64decode(content)
                plate = _extract_itscam_plate(raw_bytes) or ""
                # Extrai timestamp do JPEG (primeiros bytes ASCII contêm data)
                ts_matches = re.findall(rb'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', raw_bytes[:512])
                if ts_matches:
                    timestamp = _parse_intelbras_datetime(ts_matches[0].decode())
            except Exception as exc:
                logger.debug("Erro ao extrair dados do JPEG ITSCAM: %s", exc)

            if not plate:
                return None  # Frame sem placa detectada — ignorar

            return AlprDetection(
                camera_id=camera_id,
                tenant_id=tenant_id,
                plate=plate,
                confidence=confidence,
                manufacturer=self.manufacturer,
                timestamp=timestamp,
                raw_payload={k: v for k, v in raw.items() if k != "Picture"},  # não salva JPEG no DB
                image_b64=image_b64,
            )

        # Formato 3: DVR/NVR com Events[]
        events = raw.get("Events", [])
        if isinstance(events, list) and events:
            ev = events[0] if isinstance(events[0], dict) else {}
            plate = str(ev.get("LicensePlate") or ev.get("Plate") or "").upper().strip()
            if not plate:
                logger.debug("Intelbras normalizer: placa vazia, ignorando evento")
                return None
            conf_raw = ev.get("Confidence", 0)
            try:
                confidence = float(conf_raw) / (100.0 if float(conf_raw) > 1 else 1.0)
            except (ValueError, TypeError):
                confidence = 0.0
            timestamp = _parse_intelbras_datetime(raw.get("DateTime", ""))

        # Formato 1 (PT) e Formato 2 (EN)
        if not plate:
            plate = str(raw.get("placa") or raw.get("plate") or "").upper().strip()
            conf_raw = raw.get("confianca") or raw.get("confidence") or 0
            try:
                raw_f = float(conf_raw)
                confidence = raw_f / 100.0 if raw_f > 1.0 else raw_f
            except (ValueError, TypeError):
                confidence = 0.0
            timestamp = _parse_intelbras_datetime(
                raw.get("timestamp") or raw.get("dateTime") or ""
            )
            image_b64 = raw.get("imagem") or raw.get("image")

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
    """Converte string de data Intelbras para datetime."""
    if not value:
        return datetime.utcnow()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d%H%M%S",
    ):
        try:
            return datetime.strptime(value[:19], fmt[:len(value[:19])])
        except (ValueError, TypeError):
            continue
    return datetime.utcnow()


# Auto-registra ao importar
registry.register(IntelbrasNormalizer())
