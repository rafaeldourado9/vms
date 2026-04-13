"""Rotas HTTP do bounded context de eventos — webhooks e consultas."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from redis.asyncio import Redis

from vms.core.deps import CurrentUser, DbSession
from vms.core.rate_limit import limiter
from vms.events.domain import AlprDetection
from vms.events.normalizers.base import registry
# Importa normalizers para forçar auto-registro
import vms.events.normalizers.hikvision  # noqa: F401
import vms.events.normalizers.intelbras  # noqa: F401
import vms.events.normalizers.generic    # noqa: F401
from vms.events.repository import EventRepository
from vms.events.schemas import (
    AlprWebhookRequest,
    EventListResponse,
    MediaMTXOnNotReadyPayload,
    MediaMTXOnReadyPayload,
    MediaMTXSegmentPayload,
    VmsEventResponse,
)
from vms.events.service import EventService

logger = logging.getLogger(__name__)
router = APIRouter()

_MEDIAMTX_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")
_LIVE_PATH_RE     = re.compile(r"live/(?P<stream_key>[^/]+?)(?:\.stream)?$")


async def _get_redis(request: Request) -> Redis:
    """Extrai cliente Redis do state da aplicação."""
    return request.app.state.redis


def _event_svc(db: DbSession) -> EventService:
    """Constrói EventService com repositório."""
    return EventService(EventRepository(db))


# ─── Webhooks ALPR ────────────────────────────────────────────────────────────

@router.post(
    "/webhooks/alpr",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Webhook ALPR genérico",
    tags=["webhooks"],
)
@limiter.limit("500/minute")
async def webhook_alpr_generic(
    request: Request,
    body: AlprWebhookRequest,
    db: DbSession,
    redis: Redis = Depends(_get_redis),
) -> dict:
    """Recebe detecção ALPR no formato normalizado."""
    tenant_id = await _resolve_tenant(body.camera_id)
    detection = AlprDetection(
        camera_id=body.camera_id,
        tenant_id=tenant_id,
        plate=body.plate.upper(),
        confidence=body.confidence,
        manufacturer="generic",
        timestamp=body.timestamp,
        raw_payload=body.model_dump(mode="json"),
        image_b64=body.image_b64,
    )
    svc = _event_svc(db)
    event = await svc.ingest_alpr(detection, redis)
    return {"accepted": event is not None, "event_id": event.id if event else None}


@router.post(
    "/webhooks/alpr/{manufacturer}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Webhook ALPR por fabricante",
    tags=["webhooks"],
)
@limiter.limit("500/minute")
async def webhook_alpr_vendor(
    request: Request,
    manufacturer: str,
    body: dict,
    db: DbSession,
    camera_id: str = Query(...),
    tenant_id: str = Query(...),
    redis: Redis = Depends(_get_redis),
) -> dict:
    """Recebe payload raw do fabricante e normaliza internamente."""
    normalizer = registry.get(manufacturer)
    if not normalizer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Fabricante não suportado: '{manufacturer}'",
        )
    try:
        detection = normalizer.normalize(body, camera_id, tenant_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Payload inválido para {manufacturer}: {exc}",
        ) from exc

    svc = _event_svc(db)
    event = await svc.ingest_alpr(detection, redis)
    return {"accepted": event is not None, "event_id": event.id if event else None}


# ─── Webhooks MediaMTX ────────────────────────────────────────────────────────

@router.post(
    "/webhooks/mediamtx/on_ready",
    status_code=status.HTTP_200_OK,
    summary="Webhook MediaMTX — stream pronto",
    tags=["webhooks"],
)
async def mediamtx_on_ready(
    body: MediaMTXOnReadyPayload, request: Request, db: DbSession
) -> dict:
    """Marca câmera como online quando stream está disponível."""
    ids = _parse_mediamtx_path(body.path) or await _resolve_live_path(body.path, db)
    if not ids:
        logger.warning("Path MediaMTX inválido em on_ready: %s", body.path)
        return {"ok": True}

    tenant_id, camera_id = ids
    logger.info("Stream pronto: tenant=%s camera=%s", tenant_id, camera_id)

    from sqlalchemy import update as sa_update
    from vms.cameras.models import CameraModel
    stmt = (
        sa_update(CameraModel)
        .where(CameraModel.id == camera_id, CameraModel.tenant_id == tenant_id)
        .values(is_online=True, last_seen_at=datetime.utcnow())
    )
    await db.execute(stmt)

    from vms.core.event_bus import publish_event
    await publish_event(
        "camera.online",
        {"camera_id": camera_id, "path": body.path},
        tenant_id=tenant_id,
    )
    return {"ok": True}


@router.post(
    "/webhooks/mediamtx/on_not_ready",
    status_code=status.HTTP_200_OK,
    summary="Webhook MediaMTX — stream encerrado",
    tags=["webhooks"],
)
async def mediamtx_on_not_ready(body: MediaMTXOnNotReadyPayload, db: DbSession) -> dict:
    """Marca câmera como offline quando stream é encerrado."""
    ids = _parse_mediamtx_path(body.path) or await _resolve_live_path(body.path, db)
    if not ids:
        return {"ok": True}

    tenant_id, camera_id = ids
    logger.info("Stream encerrado: tenant=%s camera=%s", tenant_id, camera_id)

    from sqlalchemy import update as sa_update
    from vms.cameras.models import CameraModel
    stmt = (
        sa_update(CameraModel)
        .where(CameraModel.id == camera_id, CameraModel.tenant_id == tenant_id)
        .values(is_online=False)
    )
    await db.execute(stmt)

    from vms.core.event_bus import publish_event
    await publish_event(
        "camera.offline",
        {"camera_id": camera_id, "path": body.path},
        tenant_id=tenant_id,
    )
    return {"ok": True}


@router.post(
    "/webhooks/mediamtx/segment_ready",
    status_code=status.HTTP_200_OK,
    summary="Webhook MediaMTX — segmento de gravação pronto",
    tags=["webhooks"],
)
async def mediamtx_segment_ready(body: MediaMTXSegmentPayload, db: DbSession, request: Request) -> dict:
    """Indexa segmento de gravação e enqueues task batch para analytics."""
    ids = _parse_mediamtx_path(body.path) or await _resolve_live_path(body.path, db)
    if not ids:
        logger.warning("Path MediaMTX inválido em segment_ready: %s", body.path)
        return {"ok": True}

    tenant_id, camera_id = ids
    logger.info("Segmento pronto: %s -> %s", body.path, body.segment_path)

    # Indexa o segmento diretamente no banco de dados
    from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
    from vms.recordings.service import RecordingService
    svc = RecordingService(RecordingSegmentRepository(db), ClipRepository(db))
    try:
        segment = await svc.index_segment(
            tenant_id=tenant_id,
            camera_id=camera_id,
            file_path=body.segment_path,
            mediamtx_path=body.path,
        )

        # Enqueue ARQ task para processamento batch com plugins de IA
        try:
            redis = request.app.state.arq_redis
            await redis.enqueue_job(
                "task_batch_process_segment",
                segment_id=segment.id,
                file_path=body.segment_path,
                camera_id=camera_id,
                tenant_id=tenant_id,
            )
        except Exception:
            logger.debug(
                "Falha ao enqueue batch task para segmento %s (não crítico)",
                segment.id,
                exc_info=True,
            )

    except Exception:
        logger.exception("Erro ao indexar segmento: %s", body.segment_path)

    from vms.infrastructure.messaging.event_bus import publish_event
    await publish_event(
        "recording.segment_ready",
        {"camera_id": camera_id, "path": body.path, "segment_path": body.segment_path},
        tenant_id=tenant_id,
    )
    return {"ok": True}


# ─── Consulta de Eventos ──────────────────────────────────────────────────────

@router.get(
    "/events",
    response_model=EventListResponse,
    summary="Listar eventos",
    tags=["events"],
)
async def list_events(
    claims: CurrentUser,
    db: DbSession,
    event_type: str | None = Query(default=None),
    plate: str | None = Query(default=None),
    camera_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> EventListResponse:
    """Lista eventos do tenant com paginação e filtros opcionais."""
    offset = (page - 1) * page_size
    svc = _event_svc(db)
    events, total = await svc.list_events(
        tenant_id=claims.tenant_id,
        event_type=event_type,
        plate=plate,
        camera_id=camera_id,
        limit=page_size,
        offset=offset,
    )
    items = [VmsEventResponse.model_validate(e) for e in events]
    return EventListResponse.build(items, total, page, page_size)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_mediamtx_path(path: str) -> tuple[str, str] | None:
    """
    Extrai (tenant_id, camera_id) do path MediaMTX.

    Suporta dois formatos:
    - tenant-{tid}/cam-{cid} → extração direta
    - live/{stream_key}      → requer lookup no DB (ver _resolve_live_path)
    """
    match = _MEDIAMTX_PATH_RE.match(path)
    if not match:
        return None
    return match.group("tenant_id"), match.group("camera_id")


async def _resolve_live_path(path: str, db) -> tuple[str, str] | None:
    """
    Resolve (tenant_id, camera_id) para paths no formato live/{stream_key}.

    Faz lookup no banco pelo rtmp_stream_key da câmera.
    """
    live_match = _LIVE_PATH_RE.match(path)
    if not live_match:
        return None
    stream_key = live_match.group("stream_key")
    from vms.cameras.repository import CameraRepository
    repo = CameraRepository(db)
    camera = await repo.get_by_stream_key(stream_key)
    if not camera:
        return None
    return camera.tenant_id, camera.id


async def _resolve_tenant(camera_id: str) -> str:
    """Resolve tenant_id a partir do camera_id via repositório."""
    from vms.cameras.repository import CameraRepository
    from vms.core.database import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        repo = CameraRepository(session)
        camera = await repo.get_by_id(camera_id)
        if camera:
            return camera.tenant_id
    return "unknown"
