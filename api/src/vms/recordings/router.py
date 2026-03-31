"""Rotas HTTP do bounded context de gravações."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from vms.core.deps import CurrentUser, DbSession
from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
from vms.recordings.schemas import (
    ClipListResponse,
    ClipResponse,
    CreateClipRequest,
    RecordingSegmentResponse,
    SegmentListResponse,
    TimelineHourResponse,
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


@router.get(
    "/cameras/{camera_id}/timeline",
    response_model=list[TimelineHourResponse],
    summary="Timeline de gravações por hora",
    tags=["recordings"],
)
async def get_timeline(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
    started_after: datetime | None = Query(default=None),
    started_before: datetime | None = Query(default=None),
) -> list[TimelineHourResponse]:
    """
    Retorna segmentos agrupados por hora para UI de playback.

    Calcula cobertura (coverage_pct) por hora baseado na duração dos segmentos.
    """
    svc = _recording_svc(db)
    segments, _ = await svc._segments.list_by_camera(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        started_after=started_after,
        started_before=started_before,
        limit=10000,
        offset=0,
    )

    # Agrupa por hora
    hours: dict[datetime, list] = {}
    for seg in segments:
        started = seg.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        hour_key = started.replace(minute=0, second=0, microsecond=0)
        hours.setdefault(hour_key, []).append(seg)

    result = []
    for hour_dt, hour_segs in sorted(hours.items()):
        total_duration = sum(s.duration_seconds for s in hour_segs)
        coverage_pct = min(total_duration / 3600.0, 1.0)
        result.append(
            TimelineHourResponse(
                hour=hour_dt,
                segments=[RecordingSegmentResponse.model_validate(s) for s in hour_segs],
                coverage_pct=round(coverage_pct, 4),
            )
        )

    return result


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


@router.get(
    "/recordings/clips/{clip_id}",
    response_model=ClipResponse,
    summary="Status do clipe",
    tags=["recordings"],
)
async def get_clip(
    clip_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> ClipResponse:
    """Retorna status do clipe (polling para UI saber quando ficou pronto)."""
    svc = _recording_svc(db)
    clip = await svc._clips.get_by_id(clip_id, claims.tenant_id)
    if not clip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clipe não encontrado")
    return ClipResponse.model_validate(clip)


@router.get(
    "/recordings/{recording_id}/download",
    summary="URL de download de segmento",
    tags=["recordings"],
)
async def download_recording(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Retorna URL de download do arquivo de gravação (redirect para nginx)."""
    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gravação não encontrada")
    import os
    filename = os.path.basename(segment.file_path)
    download_url = f"/recordings/{filename}"
    return {"download_url": download_url, "file_path": segment.file_path}


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
