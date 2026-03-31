"""Rotas HTTP do bounded context de gravações."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, status

from vms.core.deps import CurrentUser, DbSession
from vms.core.exceptions import NotFoundError
from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
from vms.recordings.schemas import (
    ClipListResponse,
    ClipResponse,
    CreateClipRequest,
    SegmentListResponse,
    RecordingSegmentResponse,
)
from vms.recordings.service import RecordingService

router = APIRouter()


def _recording_svc(db: DbSession) -> RecordingService:
    """Constrói RecordingService com repositórios."""
    return RecordingService(
        RecordingSegmentRepository(db),
        ClipRepository(db),
    )


# ─── Segmentos ────────────────────────────────────────────────────────────────

@router.get(
    "/recordings",
    response_model=SegmentListResponse,
    summary="Listar segmentos de gravação",
    tags=["recordings"],
)
async def list_recordings(
    claims: CurrentUser,
    db: DbSession,
    camera_id: str = Query(..., description="ID da câmera"),
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> SegmentListResponse:
    """Lista segmentos de gravação de uma câmera com filtro de período."""
    offset = (page - 1) * page_size
    svc = _recording_svc(db)
    segments, total = await svc._segments.list_by_camera(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        started_after=started_after,
        started_before=started_before,
        limit=page_size,
        offset=offset,
    )
    items = [RecordingSegmentResponse.model_validate(s) for s in segments]
    return SegmentListResponse.build(items, total, page, page_size)


# ─── Clipes ───────────────────────────────────────────────────────────────────

@router.get(
    "/recordings/clips",
    response_model=ClipListResponse,
    summary="Listar clipes",
    tags=["recordings"],
)
async def list_clips(
    claims: CurrentUser,
    db: DbSession,
    camera_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ClipListResponse:
    """Lista clipes do tenant com paginação."""
    offset = (page - 1) * page_size
    svc = _recording_svc(db)
    clips, total = await svc._clips.list_by_tenant(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        limit=page_size,
        offset=offset,
    )
    items = [ClipResponse.model_validate(c) for c in clips]
    return ClipListResponse.build(items, total, page, page_size)


@router.post(
    "/recordings/clips",
    response_model=ClipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar clipe",
    tags=["recordings"],
)
async def create_clip(
    body: CreateClipRequest,
    claims: CurrentUser,
    db: DbSession,
) -> ClipResponse:
    """Solicita geração de clipe de vídeo. Processamento é assíncrono."""
    svc = _recording_svc(db)
    clip = await svc.create_clip(
        tenant_id=claims.tenant_id,
        camera_id=body.camera_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        vms_event_id=body.vms_event_id,
    )
    return ClipResponse.model_validate(clip)
