"""Rotas HTTP do bounded context de gravações."""
from __future__ import annotations

from datetime import UTC, datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, status

from vms.cameras.repository import CameraRepository
from vms.cameras.service import CameraService
from vms.core.config import get_settings
from vms.core.deps import CurrentUser, DbSession
from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
from vms.recordings.schemas import (
    ClipListResponse,
    ClipResponse,
    CreateClipRequest,
    RecordingSegmentResponse,
    SegmentListResponse,
    TimelineHourResponse,
    VodResponse,
)
from vms.recordings.service import RecordingService
from vms.iam.service import AuthService
from vms.iam.repository import ApiKeyRepository as IamRepo

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
        seg_responses = [RecordingSegmentResponse.model_validate(s) for s in hour_segs]
        result.append(TimelineHourResponse.from_segments(hour_dt, seg_responses))

    return result


# ─── VOD ─────────────────────────────────────────────────────────────────────

@router.get(
    "/cameras/{camera_id}/vod",
    response_model=VodResponse,
    summary="URL HLS VOD para playback de gravações",
    tags=["recordings"],
)
async def get_vod_url(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
    request: Request,
    from_ts: datetime = Query(..., alias="from", description="Início do período (ISO 8601)"),
    to_ts: datetime = Query(..., alias="to", description="Fim do período (ISO 8601)"),
) -> VodResponse:
    """
    Retorna URL HLS VOD para playback via MediaMTX.

    O frontend passa a URL diretamente para o HLS.js — o MediaMTX serve
    os segmentos .mp4 gravados como playlist HLS dinâmica.
    Gaps de gravação são indicados via `has_gaps=true`.
    """
    # 1. Valida câmera no tenant (isolamento multi-tenant)
    camera_svc = CameraService(CameraRepository(db))
    camera = await camera_svc.get_camera(camera_id, claims.tenant_id)

    # 2. Segmentos no intervalo — para contar e detectar gaps
    seg_repo = RecordingSegmentRepository(db)
    segments, total = await seg_repo.list_by_camera(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        started_after=from_ts,
        started_before=to_ts,
        limit=10000,
        offset=0,
    )
    if not segments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma gravação encontrada no período solicitado",
        )

    # 3. Detecta gaps (> 5s entre segmentos consecutivos)
    sorted_segs = sorted(segments, key=lambda s: s.started_at)
    has_gaps = any(
        (sorted_segs[i].started_at - sorted_segs[i - 1].ended_at).total_seconds() > 5
        for i in range(1, len(sorted_segs))
    )

    # 4. ViewerToken JWT (valida leitura no MediaMTX via read-auth hook)
    auth_svc = AuthService(user_repo=None, api_key_repo=IamRepo(db))  # type: ignore[arg-type]
    viewer_token = await auth_svc.issue_viewer_token(
        tenant_id=claims.tenant_id, camera_id=camera_id
    )

    # 5. Constrói URL de recording do MediaMTX
    #    Formato: http://HOST:8888/PATH/rec.m3u8?start=RFC3339&duration=SECS&token=JWT
    mediamtx_host = request.headers.get("X-MediaMTX-Host", "localhost")
    duration_seconds = max(1, int((to_ts - from_ts).total_seconds()))

    # Normaliza timezone para UTC e formata como RFC3339
    start_utc = from_ts.astimezone(UTC) if from_ts.tzinfo else from_ts.replace(tzinfo=UTC)
    start_str = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    hls_url = (
        f"http://{mediamtx_host}:8888/{camera.mediamtx_path}"
        f"/rec.m3u8?start={start_str}&duration={duration_seconds}&token={viewer_token}"
    )

    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)

    return VodResponse(
        hls_url=hls_url,
        token=viewer_token,
        expires_at=expires_at,
        segments_count=total,
        has_gaps=has_gaps,
    )


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
