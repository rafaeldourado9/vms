"""Webhook público para câmeras IP enviarem eventos diretamente.

Sem autenticação — câmeras não suportam JWT.
Identificação da câmera por (em ordem de prioridade):
  1. Query param ?camera_id=<uuid>  ← mais confiável, configure na URL do alarm server
  2. Campo 'camera_id'/'deviceId' no payload
  3. Stream key no payload (path live/xxx)
  4. Campo 'ipAddress' no XML do payload
  5. IP de origem da requisição → match com rtsp_url/onvif_url no DB

Endpoints expostos pelo nginx em:
  /hik_pro_connect          → alias direto (sem prefixo, compatível com config de câmera)
  /intelbras_events         → alias direto
  /webhooks/hik_pro_connect → com prefixo (ambos funcionam)
  /webhooks/intelbras_events
  /webhooks/camera_events
"""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import select

from vms.cameras.models import CameraModel
from vms.core.database import get_session_factory
from vms.events.models import VmsEventModel
from vms.events.normalizers.base import registry

logger = logging.getLogger(__name__)

# Auto-registra normalizers ao importar
import vms.events.normalizers.hikvision  # noqa: F401
import vms.events.normalizers.intelbras  # noqa: F401
import vms.events.normalizers.generic    # noqa: F401

router = APIRouter()

_STREAM_KEY_RE = re.compile(r"live/(?P<key>[a-zA-Z0-9_\-\.]+?)(?:\.stream)?$")


# ─── Body parsing ─────────────────────────────────────────────────────────────
# Hikvision "Alarm Server" envia multipart/form-data com JSON na parte
# 'anpr_result', OU application/xml (ISAPI EventNotificationAlert).
# O código antigo fazia request.json() que falha silenciosamente → body={}.

async def _parse_body(request: Request) -> dict:
    """
    Parseia o body independente do Content-Type.

    Tenta, em ordem:
    1. multipart/form-data  — Hikvision alarm server (formato principal)
    2. application/xml      — Hikvision ISAPI / Intelbras XML
    3. application/json     — maioria dos fabricantes
    4. fallback: tenta JSON, depois XML
    """
    ct = request.headers.get("content-type", "").lower()

    if "multipart" in ct:
        return await _parse_multipart(request)

    raw = await request.body()
    if not raw:
        return {}

    if "xml" in ct:
        return _parse_xml(raw)

    # JSON ou Content-Type ausente/desconhecido
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Último recurso: tenta XML
        try:
            return _parse_xml(raw)
        except ET.ParseError:
            return {}


async def _parse_multipart(request: Request) -> dict:
    """
    Extrai payload JSON do multipart enviado pela Hikvision.

    A Hikvision coloca o JSON em campos nomeados:
      'anpr_result'  → payload ANPR
      'event_info'   → evento genérico
      'alarmEvent'   → evento de alarme
    Campos binários (imagem JPEG) são ignorados.
    """
    try:
        form = await request.form()

        # Campos conhecidos da Hikvision (em ordem de preferência)
        for field in ("anpr_result", "event_info", "alarmEvent", "data", "payload"):
            val = form.get(field)
            if val and isinstance(val, str):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass

        # Qualquer campo string que pareça JSON
        for _name, val in form.multi_items():
            if isinstance(val, str) and val.strip().startswith("{"):
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, dict):
                        return parsed
                except (json.JSONDecodeError, ValueError):
                    pass

        # Fallback: campos simples como dict
        return {k: v for k, v in form.multi_items() if isinstance(v, str)}

    except Exception as exc:
        logger.debug("Falha ao parsear multipart: %s", exc)
        return {}


def _parse_xml(xml_bytes: bytes) -> dict:
    """
    Converte XML Hikvision EventNotificationAlert para dict normalizado.

    Entrada:
        <EventNotificationAlert>
            <ANPR>
                <licensePlate>ABC1234</licensePlate>
                <confidence>85</confidence>
            </ANPR>
            <dateTime>2026-04-11T10:58:07+01:00</dateTime>
            <ipAddress>192.168.1.64</ipAddress>
        </EventNotificationAlert>

    Saída:
        {
            "ANPR": {"licensePlate": "ABC1234", "confidence": "85"},
            "dateTime": "2026-04-11T10:58:07+01:00",
            "ipAddress": "192.168.1.64",
        }
    """
    root = ET.fromstring(xml_bytes)  # lança ET.ParseError se inválido
    result = _elem_to_dict(root)
    # Achata o wrapper raiz (ex: EventNotificationAlert) para o dict interior
    root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    if root_tag in result and isinstance(result[root_tag], dict):
        return result[root_tag]
    return result


def _elem_to_dict(el: ET.Element) -> dict:
    """
    Converte elemento XML em {tag: value} recursivamente, stripando namespaces.

    - Elemento folha  → {tag: "texto"}
    - Elemento pai    → {tag: {child_tag: child_value, ...}}
    - Tags duplicadas → {tag: [val1, val2, ...]}
    """
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
    children = list(el)

    if not children:
        return {tag: (el.text or "").strip()}

    child_dict: dict = {}
    for child in children:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        # Desempacota o valor filho (retorna {child_tag: val})
        child_val = _elem_to_dict(child).get(child_tag)

        if child_tag in child_dict:
            existing = child_dict[child_tag]
            if not isinstance(existing, list):
                child_dict[child_tag] = [existing]
            child_dict[child_tag].append(child_val)
        else:
            child_dict[child_tag] = child_val

    return {tag: child_dict}


# ─── Camera resolution ────────────────────────────────────────────────────────

def _get_real_ip(request: Request) -> str:
    return (
        request.headers.get("X-Real-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
    )


async def _resolve_camera(
    body: dict,
    remote_ip: str,
    camera_id_param: str | None = None,
) -> tuple[str, str] | None:
    """
    Resolve (tenant_id, camera_id) em ordem de confiabilidade:

    1. ?camera_id= query param  — integrador configurou na URL
    2. Campo camera_id/deviceId no body
    3. Stream key live/<key>
    4. Campo ipAddress no XML (câmera envia o próprio IP)
    5. IP de origem → match com rtsp_url / onvif_url no DB
    """
    # 1. Query param — mais confiável
    if camera_id_param:
        result = await _lookup_by_id(camera_id_param)
        if result:
            logger.debug("Câmera resolvida via query param: %s", camera_id_param)
            return result

    # 2. Campo direto no body
    # DeviceID = Intelbras "Nº dispos." (campo enviado no body do push)
    for key in ("camera_id", "cameraId", "DeviceID", "deviceId", "device_id", "deviceSerial", "serialNo"):
        cam_id = body.get(key)
        if cam_id and isinstance(cam_id, str):
            result = await _lookup_by_id(str(cam_id))
            if result:
                logger.debug("Câmera resolvida via body[%s]: %s", key, cam_id)
                return result

    # 3. Stream key
    path = body.get("path", body.get("stream_key", ""))
    if m := _STREAM_KEY_RE.match(str(path)):
        result = await _lookup_by_stream_key(m.group("key"))
        if result:
            logger.debug("Câmera resolvida via stream_key: %s", m.group("key"))
            return result

    # 4. IP no payload XML (câmera Hikvision inclui <ipAddress>)
    payload_ip = body.get("ipAddress", "")
    if payload_ip and payload_ip != remote_ip:
        result = await _lookup_by_ip(str(payload_ip))
        if result:
            logger.debug("Câmera resolvida via ipAddress no payload: %s", payload_ip)
            return result

    # 5. IP de origem
    if remote_ip:
        result = await _lookup_by_ip(remote_ip)
        if result:
            logger.debug("Câmera resolvida via IP de origem: %s", remote_ip)
            return result

    return None


async def _lookup_by_id(cam_id: str) -> tuple[str, str] | None:
    factory = get_session_factory()
    async with factory() as session:
        cam = await session.scalar(
            select(CameraModel).where(
                CameraModel.id == cam_id,
                CameraModel.is_active.is_(True),
            )
        )
        return (cam.tenant_id, cam.id) if cam else None


async def _lookup_by_stream_key(stream_key: str) -> tuple[str, str] | None:
    factory = get_session_factory()
    async with factory() as session:
        cam = await session.scalar(
            select(CameraModel).where(
                CameraModel.rtmp_stream_key == stream_key,
                CameraModel.is_active.is_(True),
            )
        )
        return (cam.tenant_id, cam.id) if cam else None


async def _lookup_by_ip(ip: str) -> tuple[str, str] | None:
    """Busca câmera que contenha o IP em rtsp_url ou onvif_url."""
    if not ip:
        return None
    factory = get_session_factory()
    async with factory() as session:
        cams = await session.scalars(
            select(CameraModel).where(CameraModel.is_active.is_(True))
        )
        for cam in cams.all():
            for url in (cam.rtsp_url, cam.onvif_url):
                if url and ip in url:
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


async def _publish_sse(tenant_id: str, event_type: str, data: dict) -> None:
    """Publica evento no canal SSE do tenant."""
    try:
        from vms.infrastructure.messaging.event_bus import publish_event
        await publish_event(event_type, data, tenant_id=tenant_id)
    except Exception as exc:
        logger.debug("Falha ao publicar SSE (não crítico): %s", exc)


# ─── Hikvision ───────────────────────────────────────────────────────────────

@router.post(
    "/hik_pro_connect",
    status_code=status.HTTP_200_OK,
    summary="Webhook Hikvision Alarm Server",
    tags=["webhooks-public"],
)
async def hikvision_webhook(
    request: Request,
    camera_id: str | None = Query(
        None,
        description=(
            "UUID da câmera (configure na URL do Alarm Server). "
            "Exemplo: /hik_pro_connect?camera_id=<uuid>"
        ),
    ),
) -> dict:
    """
    Recebe notificações do Alarm Server Hikvision.

    **Como configurar na câmera:**
    Configuração → Evento → Definição do Alarme → Servidor de Alarme:
    - IP/Host: `<seu-dominio>`
    - URL:     `/hik_pro_connect?camera_id=<uuid-da-camera>`
    - Porta:   `80`
    - Protocolo: `HTTP`

    Suporta: multipart/form-data, application/xml, application/json.
    """
    body = await _parse_body(request)
    remote_ip = _get_real_ip(request)

    logger.info(
        "Hikvision webhook | ip=%s camera_id_param=%s ct=%s body_keys=%s",
        remote_ip,
        camera_id,
        request.headers.get("content-type", "?"),
        list(body.keys()) if body else "empty",
    )

    cam_info = await _resolve_camera(body, remote_ip, camera_id)
    if not cam_info:
        logger.warning(
            "Câmera não identificada no webhook Hikvision | ip=%s body_keys=%s",
            remote_ip,
            list(body.keys()),
        )
        # Retorna 200 para a câmera não entrar em retry loop agressivo
        return {
            "ok": False,
            "reason": "camera_not_found",
            "hint": "Add ?camera_id=<uuid> to the Alarm Server URL",
        }

    tenant_id, cam_id = cam_info

    # Tenta normalizar como ANPR
    normalizer = registry.get("hikvision")
    if normalizer and normalizer.can_handle(body):
        try:
            detection = normalizer.normalize(body, cam_id, tenant_id)
            event = await _store_event(
                tenant_id, cam_id,
                event_type="alpr_detected",
                payload=body,
                plate=detection.plate,
                confidence=detection.confidence,
            )
            # Publica SSE para frontend
            await _publish_sse(tenant_id, "alpr.detected", {
                "plate": detection.plate,
                "confidence": detection.confidence,
                "camera_id": cam_id,
                "event_id": str(event.id) if event else None,
            })
            logger.info("ANPR Hikvision | placa=%s camera=%s", detection.plate, cam_id)
            return {"ok": True, "event_id": str(event.id) if event else None}
        except Exception as exc:
            logger.error("Erro ao normalizar ANPR Hikvision: %s", exc)

    # Evento genérico (motion, alarm, etc.)
    event_type = "hikvision_event"
    if body.get("eventType"):
        event_type = f"hikvision_{body['eventType']}"
    elif body.get("EventNotificationAlert", {}).get("eventType"):  # type: ignore[union-attr]
        event_type = f"hikvision_{body['EventNotificationAlert']['eventType']}"

    event = await _store_event(tenant_id, cam_id, event_type=event_type, payload=body)
    # Publica SSE para evento genérico
    await _publish_sse(tenant_id, event_type, {
        "camera_id": cam_id,
        "event_id": str(event.id) if event else None,
    })
    return {"ok": True, "event_id": str(event.id) if event else None}


# ─── Intelbras ────────────────────────────────────────────────────────────────

@router.post(
    "/intelbras_events",
    status_code=status.HTTP_200_OK,
    summary="Webhook Intelbras",
    tags=["webhooks-public"],
)
async def intelbras_webhook(
    request: Request,
    camera_id: str | None = Query(None, description="UUID da câmera"),
) -> dict:
    """
    Recebe eventos de câmeras/DVR/NVR Intelbras.

    **Como configurar:**
    - URL: `http://<seu-dominio>/intelbras_events?camera_id=<uuid>`
    """
    body = await _parse_body(request)
    remote_ip = _get_real_ip(request)

    logger.info(
        "Intelbras webhook | ip=%s camera_id_param=%s body_keys=%s",
        remote_ip,
        camera_id,
        list(body.keys()) if body else "empty",
    )

    cam_info = await _resolve_camera(body, remote_ip, camera_id)
    if not cam_info:
        logger.warning("Câmera não identificada no webhook Intelbras | ip=%s", remote_ip)
        return {
            "ok": False,
            "reason": "camera_not_found",
            "hint": "Add ?camera_id=<uuid> to the URL",
        }

    tenant_id, cam_id = cam_info

    normalizer = registry.get("intelbras")
    if normalizer and normalizer.can_handle(body):
        try:
            detection = normalizer.normalize(body, cam_id, tenant_id)
            event = await _store_event(
                tenant_id, cam_id,
                event_type="alpr_detected",
                payload=body,
                plate=detection.plate,
                confidence=detection.confidence,
            )
            # Publica SSE para frontend
            await _publish_sse(tenant_id, "alpr.detected", {
                "plate": detection.plate,
                "confidence": detection.confidence,
                "camera_id": cam_id,
                "event_id": str(event.id) if event else None,
            })
            logger.info("ANPR Intelbras | placa=%s camera=%s", detection.plate, cam_id)
            return {"ok": True, "event_id": str(event.id) if event else None}
        except Exception as exc:
            logger.error("Erro ao normalizar Intelbras: %s", exc)

    # Fallback genérico
    event_type = f"intelbras_{body.get('eventType', body.get('type', body.get('event', 'event')))}"
    plate = body.get("plate") or body.get("licensePlate") or body.get("placa")
    confidence = body.get("confidence") or body.get("confianca")

    event = await _store_event(
        tenant_id, cam_id,
        event_type=event_type,
        payload=body,
        plate=str(plate) if plate else None,
        confidence=float(confidence) if confidence else None,
    )
    # Publica SSE para evento genérico
    await _publish_sse(tenant_id, event_type, {
        "camera_id": cam_id,
        "plate": plate,
        "event_id": str(event.id) if event else None,
    })
    return {"ok": True, "event_id": str(event.id) if event else None}


# ─── Genérico ────────────────────────────────────────────────────────────────

@router.post(
    "/camera_events",
    status_code=status.HTTP_200_OK,
    summary="Webhook genérico",
    tags=["webhooks-public"],
)
async def generic_camera_webhook(
    request: Request,
    camera_id: str | None = Query(None),
) -> dict:
    """Endpoint genérico para qualquer câmera/fabricante."""
    body = await _parse_body(request)
    remote_ip = _get_real_ip(request)

    cam_info = await _resolve_camera(body, remote_ip, camera_id)
    if not cam_info:
        logger.warning("Câmera não identificada em camera_events | ip=%s", remote_ip)
        return {"ok": False, "reason": "camera_not_found"}

    tenant_id, cam_id = cam_info

    for mfr, normalizer in registry._normalizers.items():
        if normalizer.can_handle(body):
            try:
                detection = normalizer.normalize(body, cam_id, tenant_id)
                event = await _store_event(
                    tenant_id, cam_id,
                    event_type="alpr_detected",
                    payload=body,
                    plate=detection.plate,
                    confidence=detection.confidence,
                )
                # Publica SSE para frontend
                await _publish_sse(tenant_id, "alpr.detected", {
                    "plate": detection.plate,
                    "confidence": detection.confidence,
                    "camera_id": cam_id,
                    "manufacturer": mfr,
                    "event_id": str(event.id) if event else None,
                })
                return {"ok": True, "manufacturer": mfr, "event_id": str(event.id) if event else None}
            except Exception as exc:
                logger.error("Erro ao normalizar %s: %s", mfr, exc)

    event_type = body.get("eventType", body.get("type", "camera_event"))
    plate = body.get("plate") or body.get("licensePlate")
    confidence = body.get("confidence")

    event = await _store_event(
        tenant_id, cam_id,
        event_type=f"camera_{event_type}",
        payload=body,
        plate=str(plate) if plate else None,
        confidence=float(confidence) if confidence else None,
    )
    # Publica SSE para evento genérico
    await _publish_sse(tenant_id, f"camera_{event_type}", {
        "camera_id": cam_id,
        "plate": plate,
        "event_id": str(event.id) if event else None,
    })
    return {"ok": True, "event_id": str(event.id) if event else None}
