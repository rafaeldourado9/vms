"""Webhook público para câmeras IP enviarem eventos diretamente.

Sem autenticação — câmeras não suportam JWT. A identificação da câmera
é feita por IP de origem + stream_key no payload.

Endpoints:
    POST /hik_pro_connect      — Hikvision / Hik-Connect (ISAPI/ANPR/Alarm)
    POST /intelbras_events     — Intelbras (VMD/ANPR/Alarm)
    POST /camera_events        — Genérico (qualquer fabricante)
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from vms.cameras.domain import CameraManufacturer
from vms.cameras.models import CameraModel
from vms.core.database import get_session_factory
from vms.events.domain import AlprDetection, VmsEvent
from vms.events.models import VmsEventModel
from vms.events.normalizers.base import registry

logger = logging.getLogger(__name__)

# Importa normalizers para auto-registro
import vms.events.normalizers.hikvision  # noqa: F401
import vms.events.normalizers.intelbras  # noqa: F401
import vms.events.normalizers.generic    # noqa: F401

router = APIRouter()

# Regex para extrair stream_key de payloads
_STREAM_KEY_RE = re.compile(r"live/(?P<key>[a-zA-Z0-9_\-\.]+?)(?:\.stream)?$")
_CAMERA_ID_RE  = re.compile(r"camera[_-]?id[\"']?\s*[:=]\s*[\"']?(?P<id>[a-f0-9\-]+)", re.I)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_real_ip(request: Request) -> str:
    """Retorna o IP real do cliente, lendo X-Real-IP / X-Forwarded-For quando disponível."""
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )


async def _resolve_camera_from_payload(body: dict) -> tuple[str, str] | None:
    """
    Tenta resolver (tenant_id, camera_id) a partir do payload recebido.

    Estratégias:
    1. Campo direto 'camera_id' ou 'deviceId'
    2. Stream key no formato 'live/xxx' → lookup no DB
    3. IP de origem → match com câmera cadastrada (RTSP URL contém IP)
    """
    # 1. Campo direto
    for key in ("camera_id", "cameraId", "deviceId", "device_id", "channelID"):
        cam_id = body.get(key)
        if cam_id:
            return await _lookup_camera_by_id(cam_id)

    # 2. Stream key
    path = body.get("path", body.get("stream_key", ""))
    m = _STREAM_KEY_RE.match(str(path))
    if m:
        return await _lookup_camera_by_stream_key(m.group("key"))

    return None


async def _lookup_camera_by_id(cam_id: str) -> tuple[str, str] | None:
    """Busca câmera por ID (UUID) e retorna (tenant_id, camera_id)."""
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CameraModel).where(
            CameraModel.id == cam_id,
            CameraModel.is_active.is_(True),
        )
        cam = await session.scalar(stmt)
        if cam:
            return cam.tenant_id, cam.id
    return None


async def _lookup_camera_by_stream_key(stream_key: str) -> tuple[str, str] | None:
    """Busca câmera por stream_key RTMP."""
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CameraModel).where(
            CameraModel.rtmp_stream_key == stream_key,
            CameraModel.is_active.is_(True),
        )
        cam = await session.scalar(stmt)
        if cam:
            return cam.tenant_id, cam.id
    return None


async def _lookup_camera_by_ip(remote_ip: str) -> tuple[str, str] | None:
    """Busca câmera cujo RTSP URL contenha o IP de origem."""
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CameraModel).where(
            CameraModel.is_active.is_(True),
            CameraModel.rtsp_url.isnot(None),
        )
        cameras = await session.scalars(stmt)
        for cam in cameras.all():
            if cam.rtsp_url and remote_ip in cam.rtsp_url:
                return cam.tenant_id, cam.id
    return None


async def _store_event(
    tenant_id: str,
    camera_id: str,
    event_type: str,
    payload: dict,
    plate: str | None = None,
    confidence: float | None = None,
) -> VmsEventModel | None:
    """Persiste evento no banco."""
    factory = get_session_factory()
    async with factory() as session:
        event = VmsEventModel(
            tenant_id=tenant_id,
            camera_id=camera_id,
            event_type=event_type,
            plate=plate,
            confidence=confidence,
            payload=payload,
            occurred_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        await session.refresh(event)
        await session.commit()
        return event


# ─── Hik Pro Connect / Hikvision ISAPI ───────────────────────────────────────

@router.post(
    "/hik_pro_connect",
    status_code=status.HTTP_200_OK,
    summary="Webhook Hikvision / Hik-Connect",
    tags=["webhooks-public"],
)
async def hikvision_webhook(request: Request) -> dict:
    """
    Recebe eventos de câmeras Hikvision.

    Suporta:
    - ANPR (detecção de placa)
    - Alarme (motion, tampering, video loss)
    - ISAPI Notification

    Exemplo de payload ANPR:
    {
        "ANPR": {"licensePlate": "ABC1234", "confidence": 85},
        "dateTime": "20260330123456",
        "pictureBase64": "..."
    }

    Exemplo de payload Alarm:
    {
        "EventNotificationAlert": {
            "eventType": "motion",
            "DateTime": {"year": 2026, "month": 4, "day": 10}
        }
    }
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    logger.info("Hikvision webhook recebido: %s", body.keys() if isinstance(body, dict) else "invalid")

    # Tenta resolver câmera
    remote_ip = _get_real_ip(request)
    cam_info = await _resolve_camera_from_payload(body)
    if not cam_info:
        cam_info = await _lookup_camera_by_ip(remote_ip)
    if not cam_info:
        logger.warning("Câmera não identificada no webhook Hikvision (IP=%s)", remote_ip)
        return {"ok": False, "reason": "camera_not_found"}

    tenant_id, camera_id = cam_info

    # Detecta tipo de evento
    if "ANPR" in body:
        # Evento ANPR — usa normalizador
        normalizer = registry.get("hikvision")
        if normalizer and normalizer.can_handle(body):
            try:
                detection = normalizer.normalize(body, camera_id, tenant_id)
                event = await _store_event(
                    tenant_id, camera_id,
                    event_type="alpr_detected",
                    payload=body,
                    plate=detection.plate,
                    confidence=detection.confidence,
                )
                logger.info("ANPR Hikvision: placa=%s camera=%s", detection.plate, camera_id)
                return {"ok": True, "event_id": str(event.id) if event else None}
            except Exception as exc:
                logger.error("Erro ao normalizar ANPR Hikvision: %s", exc)

    # Evento genérico (motion, alarm, etc.)
    event_type = "hikvision_event"
    if "EventNotificationAlert" in body:
        alert = body["EventNotificationAlert"]
        event_type = f"hikvision_{alert.get('eventType', 'unknown')}"
    elif "eventType" in body:
        event_type = f"hikvision_{body['eventType']}"

    plate = body.get("ANPR", {}).get("licensePlate")
    confidence = body.get("ANPR", {}).get("confidence")
    if confidence:
        confidence = float(confidence) / 100.0

    event = await _store_event(
        tenant_id, camera_id,
        event_type=event_type,
        payload=body,
        plate=plate,
        confidence=confidence,
    )

    return {"ok": True, "event_id": str(event.id) if event else None}


# ─── Intelbras Events ────────────────────────────────────────────────────────

@router.post(
    "/intelbras_events",
    status_code=status.HTTP_200_OK,
    summary="Webhook Intelbras",
    tags=["webhooks-public"],
)
async def intelbras_webhook(request: Request) -> dict:
    """
    Recebe eventos de câmeras Intelbras.

    Suporta payloads no padrão Intelbras/VMD/ANPR.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    logger.info("Intelbras webhook recebido: %s", body.keys() if isinstance(body, dict) else "invalid")

    remote_ip = _get_real_ip(request)
    cam_info = await _resolve_camera_from_payload(body)
    if not cam_info:
        cam_info = await _lookup_camera_by_ip(remote_ip)
    if not cam_info:
        logger.warning("Câmera não identificada no webhook Intelbras (IP=%s)", remote_ip)
        return {"ok": False, "reason": "camera_not_found"}

    tenant_id, camera_id = cam_info

    # Tenta usar normalizador Intelbras
    normalizer = registry.get("intelbras")
    if normalizer and normalizer.can_handle(body):
        try:
            detection = normalizer.normalize(body, camera_id, tenant_id)
            event = await _store_event(
                tenant_id, camera_id,
                event_type="alpr_detected",
                payload=body,
                plate=detection.plate,
                confidence=detection.confidence,
            )
            return {"ok": True, "event_id": str(event.id) if event else None}
        except Exception as exc:
            logger.error("Erro ao normalizar Intelbras: %s", exc)

    # Fallback genérico
    event_type = f"intelbras_{body.get('eventType', body.get('type', 'event'))}"
    plate = body.get("plate") or body.get("licensePlate")
    confidence = body.get("confidence")

    event = await _store_event(
        tenant_id, camera_id,
        event_type=event_type,
        payload=body,
        plate=plate,
        confidence=float(confidence) if confidence else None,
    )

    return {"ok": True, "event_id": str(event.id) if event else None}


# ─── Generic Camera Events ───────────────────────────────────────────────────

@router.post(
    "/camera_events",
    status_code=status.HTTP_200_OK,
    summary="Webhook genérico para câmeras",
    tags=["webhooks-public"],
)
async def generic_camera_webhook(request: Request) -> dict:
    """
    Endpoint genérico para qualquer câmera enviar eventos.

    Payload mínimo esperado:
    {
        "camera_id": "uuid-da-camera",
        "eventType": "motion|alarm|anpr",
        "plate": "ABC1234",           // opcional
        "confidence": 0.85,           // opcional
        "timestamp": "2026-04-10T12:00:00Z"
    }

    Se camera_id não for fornecido, tenta identificar pelo IP de origem.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    remote_ip = _get_real_ip(request)
    cam_info = await _resolve_camera_from_payload(body)
    if not cam_info:
        cam_info = await _lookup_camera_by_ip(remote_ip)
    if not cam_info:
        logger.warning("Câmera não identificada em camera_events (IP=%s)", remote_ip)
        return {"ok": False, "reason": "camera_not_found"}

    tenant_id, camera_id = cam_info

    # Tenta usar qualquer normalizador que aceite o payload
    if isinstance(body, dict):
        for mfr, normalizer in registry._normalizers.items():
            if normalizer.can_handle(body):
                try:
                    detection = normalizer.normalize(body, camera_id, tenant_id)
                    event = await _store_event(
                        tenant_id, camera_id,
                        event_type="alpr_detected",
                        payload=body,
                        plate=detection.plate,
                        confidence=detection.confidence,
                    )
                    return {"ok": True, "manufacturer": mfr, "event_id": str(event.id) if event else None}
                except Exception as exc:
                    logger.error("Erro ao normalizar %s: %s", mfr, exc)

    # Fallback genérico
    event_type = body.get("eventType", body.get("type", "camera_event"))
    plate = body.get("plate") or body.get("licensePlate")
    confidence = body.get("confidence")

    event = await _store_event(
        tenant_id, camera_id,
        event_type=f"camera_{event_type}",
        payload=body,
        plate=plate,
        confidence=float(confidence) if confidence else None,
    )

    return {"ok": True, "event_id": str(event.id) if event else None}
