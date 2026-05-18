"""Rotas HTTP do bounded context de gravações."""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from vms.shared.api.dependencies import CurrentUser, DbSession
from vms.infrastructure.middleware.audit_action import audit_action
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
from vms.shared.value_objects import Sha256Hash

logger = logging.getLogger(__name__)

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
    started_after: str | None = Query(default=None, description="Filtro inicial (ISO 8601)"),
    started_before: str | None = Query(default=None, description="Filtro final (ISO 8601)"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> SegmentListResponse:
    """Lista segmentos de gravação de uma câmera com filtro de período."""
    # Parse manual dos datetimes para evitar 422 em formatos inválidos
    from datetime import datetime as DT
    
    parsed_after: DT | None = None
    parsed_before: DT | None = None
    
    if started_after:
        try:
            parsed_after = DT.fromisoformat(started_after.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Formato de data inválido para started_after: {started_after}. Use ISO 8601."
            )
    
    if started_before:
        try:
            parsed_before = DT.fromisoformat(started_before.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Formato de data inválido para started_before: {started_before}. Use ISO 8601."
            )
    
    offset = (page - 1) * page_size
    svc = _recording_svc(db)
    segments, total = await svc._segments.list_by_camera(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        started_after=parsed_after,
        started_before=parsed_before,
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
    started_after: str | None = Query(default=None),
    started_before: str | None = Query(default=None),
) -> list[TimelineHourResponse]:
    """
    Retorna segmentos agrupados por hora para UI de playback.

    Calcula cobertura (coverage_pct) por hora baseado na duração dos segmentos.
    """
    from datetime import datetime as DT

    # Parse datetimes manualmente
    parsed_after: DT | None = None
    parsed_before: DT | None = None
    if started_after:
        try:
            parsed_after = DT.fromisoformat(started_after.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
    if started_before:
        try:
            parsed_before = DT.fromisoformat(started_before.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass

    svc = _recording_svc(db)
    segments, _ = await svc._segments.list_by_camera(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        started_after=parsed_after,
        started_before=parsed_before,
        limit=10000,
        offset=0,
    )

    # Agrupa por hora
    hours: dict[int, list] = {}
    for seg in segments:
        started = seg.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        hour_key = started.hour  # 0-23
        hours.setdefault(hour_key, []).append(seg)

    result = []
    for hour_int, hour_segs in sorted(hours.items()):
        total_duration = sum(s.duration_seconds for s in hour_segs)
        coverage_pct = min(total_duration / 3600.0, 1.0)
        result.append(
            TimelineHourResponse(
                hour=hour_int,
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
@audit_action("recording.downloaded", resource_type="recording", id_param="recording_id")
async def download_recording(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """Retorna URL de download do arquivo de gravação servido pelo nginx."""
    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gravação não encontrada")
    # file_path é /recordings/tenant-X/cam-Y/YYYY/MM/DD/HH-MM-SS.mp4
    # Nginx serve /recordings/ com alias /recordings/ — URL = file_path direto
    download_url = segment.file_path
    return {"download_url": download_url, "file_path": segment.file_path}


@router.post(
    "/recordings/clips",
    response_model=ClipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar clipe",
    tags=["recordings"],
)
@audit_action("recording.clip_created", resource_type="clip")
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


# ─── Day HLS (playlist customizado servido pela API) ────────────────────────

@router.get(
    "/cameras/{camera_id}/recordings/day-hls.m3u8",
    summary="Playlist HLS-VOD do dia inteiro (m3u8 montado a partir dos fMP4)",
    tags=["recordings"],
    include_in_schema=False,
)
async def get_day_hls_playlist(
    camera_id: str,
    request: Request,
    db: DbSession,
    date: str = Query(..., description="YYYY-MM-DD"),
    token: str = Query(..., description="Viewer token JWT (?token=...)"),
) -> Response:
    """Serve o playlist HLS-VOD com auth via query token (compatível com <video>)."""
    from vms.infrastructure.security import decode_token

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") not in ("viewer", "access"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token inválido")

    tenant_id = payload.get("tenant_id")
    token_camera = payload.get("camera_id")
    if not tenant_id or (token_camera and token_camera != camera_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token não autoriza essa câmera")

    try:
        day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Data inválida: {date}")

    # Cache stores the playlist WITHOUT token so all users share the same cache.
    # Token is injected at response time via string replacement.
    _SEG_PATH_PREFIX = "/api/v1/recordings/segment?path="
    _SEG_TOKEN_PREFIX = f"/api/v1/recordings/segment?token={token}&path="

    cache_key = f"day-hls:{tenant_id}:{camera_id}:{date}"
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            content = cached.decode() if isinstance(cached, bytes) else cached
            return Response(
                content=content.replace(_SEG_PATH_PREFIX, _SEG_TOKEN_PREFIX),
                media_type="application/vnd.apple.mpegurl",
                headers={
                    "Cache-Control": "private, max-age=30",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Range",
                    "X-Cache": "HIT",
                },
            )

    svc = _recording_svc(db)
    playlist = await svc.build_day_playlist(tenant_id=tenant_id, camera_id=camera_id, day=day)
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem gravações")

    if redis is not None:
        await redis.set(cache_key, playlist, ex=30)

    return Response(
        content=playlist.replace(_SEG_PATH_PREFIX, _SEG_TOKEN_PREFIX),
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "private, max-age=30",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Range",
            "X-Cache": "MISS",
        },
    )


@router.get(
    "/recordings/segment",
    summary="Stream autenticado de segmento TS",
    tags=["recordings"],
    include_in_schema=False,
)
async def stream_segment(
    token: str = Query(..., description="Viewer token JWT"),
    path: str = Query(..., description="Caminho relativo a /recordings/"),
) -> Response:
    """
    Serve um chunk .ts autenticado via JWT no query param.

    Chamado pelo hls.js para cada chunk da playlist HLS-VOD.
    O token e o tenant_id são validados; o path é verificado contra
    path traversal e isolamento de tenant.
    """
    import os

    from fastapi.responses import FileResponse
    from vms.infrastructure.security import decode_token

    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") not in ("viewer", "access"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tipo de token inválido")

    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token sem tenant")

    _RECORDINGS_ROOT = "/recordings"
    safe_path = os.path.normpath(os.path.join(_RECORDINGS_ROOT, path))

    # Path traversal guard
    if not safe_path.startswith(_RECORDINGS_ROOT + "/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caminho inválido")

    # Tenant isolation: path must belong to this tenant's directory
    if f"/tenant-{tenant_id}/" not in (safe_path + "/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Segmento de outro tenant")

    if not os.path.isfile(safe_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segmento não encontrado")

    return FileResponse(safe_path, media_type="video/mp2t")


@router.get(
    "/cameras/{camera_id}/recordings/day-hls",
    summary="Metadados do playlist HLS do dia (URL + intervals)",
    tags=["recordings"],
)
async def get_day_hls(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
    date: str = Query(..., description="Dia a reproduzir (YYYY-MM-DD)"),
) -> dict:
    """
    Retorna metadados do playlist HLS-VOD do dia: URL do .m3u8 +
    `intervals` (gaps na gravação) + `window_seconds` (duração total).

    O playlist em si é servido por `/cameras/{id}/recordings/day-hls.m3u8`
    e referencia os fMP4 já gravados em disco (servidos pelo nginx).
    """
    try:
        day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data inválida: {date}. Use YYYY-MM-DD.",
        )

    svc = _recording_svc(db)
    result = await svc.prepare_day_hls(
        tenant_id=claims.tenant_id,
        camera_id=camera_id,
        day=day,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma gravação encontrada nesse dia",
        )
    return result


# ─── HLS Playback via MediaMTX path temporário ───────────────────────────────

@router.post(
    "/recordings/{recording_id}/hls",
    summary="Preparar stream HLS de gravação",
    tags=["recordings"],
)
async def prepare_hls_playback(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Cria path temporário no MediaMTX para streaming HLS de um segmento gravado.

    O MediaMTX lê o MP4 e remux para HLS sem reencoding. O path expira
    automaticamente após 1h de ociosidade (sourceOnDemandCloseAfter).

    Retorno::

        {
          "hls_url": "/hls/pb-{recording_id}/index.m3u8",
          "path_name": "pb-{recording_id}",
          "recording_id": "...",
          "camera_id": "...",
          "started_at": "2025-02-05T15:30:00+00:00",
          "duration_seconds": 60.0
        }
    """
    from vms.cameras.mediamtx import MediaMTXClient

    svc = _recording_svc(db)
    result = await svc.prepare_hls_playback(
        tenant_id=claims.tenant_id,
        recording_id=recording_id,
        mediamtx_client=MediaMTXClient(),
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gravação não encontrada",
        )
    return result


@router.delete(
    "/recordings/{recording_id}/hls",
    summary="Remover stream HLS temporário",
    tags=["recordings"],
)
async def remove_hls_playback(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Remove o path temporário do MediaMTX. Chamar quando o player fechar.

    O path também expira automaticamente após 1h ocioso — esta rota é
    apenas para cleanup imediato (libera recursos no MediaMTX mais cedo).
    """
    from vms.cameras.mediamtx import MediaMTXClient

    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gravação não encontrada",
        )

    path_name = f"pb-{recording_id}"
    client = MediaMTXClient()
    await client.remove_path(path_name)
    return {"removed": True, "path_name": path_name}


# ─── Cadeia de Custódia (Sprint 9) ───────────────────────────────────────────

@router.get(
    "/recordings/{recording_id}/verify-integrity",
    summary="Verificar integridade de gravação",
    tags=["recordings", "custody"],
)
@audit_action("recording.integrity_verified", resource_type="recording", id_param="recording_id")
async def verify_integrity(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Verifica integridade SHA-256 de um segmento de gravação.

    Se o hash não estiver armazenado (indexação antiga), calcula agora.
    Compara hash armazenado vs hash atual do arquivo.
    Se violação: registra ALERT no audit log.
    """
    import os

    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gravação não encontrada")

    # Verificar se arquivo existe
    if not os.path.exists(segment.file_path):
        return {
            "verified": False,
            "reason": "file_not_found",
            "stored_hash": segment.sha256_hash.value if segment.sha256_hash else None,
            "current_hash": None,
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    # Calcular hash atual
    try:
        current_hash = Sha256Hash.from_file(segment.file_path)
    except Exception as exc:
        logger.error("Falha ao calcular SHA-256 para %s: %s", segment.file_path, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao calcular hash: {exc}",
        )

    # Se não há hash armazenado, salvar agora (indexação antiga)
    stored_hash = segment.sha256_hash
    if stored_hash is None:
        await svc._segments.update_integrity(
            segment_id=recording_id,
            tenant_id=claims.tenant_id,
            sha256_hash=current_hash.value,
            integrity_verified_at=datetime.now(timezone.utc),
        )
        stored_hash = current_hash
    else:
        # Atualizar timestamp de verificação
        await svc._segments.update_integrity(
            segment_id=recording_id,
            tenant_id=claims.tenant_id,
            integrity_verified_at=datetime.now(timezone.utc),
        )

    # Comparar hashes
    is_verified = stored_hash.value == current_hash.value

    if not is_verified:
        logger.critical(
            "VIOLAÇÃO DE INTEGRIDADE: recording_id=%s stored=%s current=%s",
            recording_id,
            stored_hash.value,
            current_hash.value,
        )

    return {
        "verified": is_verified,
        "stored_hash": stored_hash.value,
        "current_hash": current_hash.value,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/recordings/{recording_id}/custody-chain",
    summary="Cadeia de custódia de gravação",
    tags=["recordings", "custody"],
)
async def get_custody_chain(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Retorna histórico completo de acessos e verificacoes de uma gravação.

    Inclui: indexação, verificações de integridade, downloads, exports forenses.
    """
    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gravação não encontrada")

    # Custody chain é armazenada como JSONB no segmento
    custody_chain = getattr(segment, 'custody_chain', []) or []

    return {
        "recording_id": recording_id,
        "tenant_id": claims.tenant_id,
        "custody_chain": custody_chain,
        "total_entries": len(custody_chain),
    }


@router.post(
    "/recordings/{recording_id}/export-forensic",
    summary="Export forense de gravação",
    tags=["recordings", "custody"],
)
@audit_action("recording.exported_forensic", resource_type="recording", id_param="recording_id")
async def export_forensic(
    recording_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> dict:
    """
    Gera pacote forense ZIP para uso legal/investigativo.

    Contém:
    - recording.mp4 (cópia do original)
    - metadata.json (dados do segmento + SHA-256)
    - custody_chain.json (cadeia de custódia completa)
    - integrity_report.txt (relatório de integridade)
    - checksum.sha256 (arquivo de checksum)

    O ZIP é assinado com HMAC-SHA256 para autenticidade.
    """
    import io
    import json
    import os
    import zipfile
    from datetime import datetime as DT

    from vms.infrastructure.security import sign_webhook_payload

    svc = _recording_svc(db)
    segment = await svc._segments.get_by_id(recording_id, claims.tenant_id)
    if not segment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gravação não encontrada")

    # Verificar se arquivo existe
    if not os.path.exists(segment.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de gravação não encontrado")

    # Calcular hash atual para verificação
    try:
        current_hash = Sha256Hash.from_file(segment.file_path)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Falha ao calcular hash: {exc}")

    # Verificar integridade
    is_verified = segment.sha256_hash.value == current_hash.value if segment.sha256_hash else True

    # Gerar ZIP em memória
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. recording.mp4
        with open(segment.file_path, 'rb') as f:
            zf.writestr('recording.mp4', f.read())

        # 2. metadata.json
        metadata = {
            "recording_id": segment.id,
            "tenant_id": segment.tenant_id,
            "camera_id": segment.camera_id,
            "file_path": segment.file_path,
            "started_at": segment.started_at.isoformat(),
            "ended_at": segment.ended_at.isoformat(),
            "duration_seconds": segment.duration_seconds,
            "size_bytes": segment.size_bytes,
            "sha256_hash": segment.sha256_hash.value if segment.sha256_hash else None,
            "integrity_verified": is_verified,
            "exported_at": DT.now(timezone.utc).isoformat(),
            "exported_by": claims.user_id,
        }
        zf.writestr('metadata.json', json.dumps(metadata, indent=2))

        # 3. custody_chain.json
        custody_chain = getattr(segment, 'custody_chain', []) or []
        custody_chain.append({
            "action": "recording.exported_forensic",
            "timestamp": DT.now(timezone.utc).isoformat(),
            "actor": claims.user_id,
            "user_email": getattr(claims, 'email', None),
        })
        zf.writestr('custody_chain.json', json.dumps(custody_chain, indent=2))

        # 4. integrity_report.txt
        report = f"""INTEGRITY REPORT
==================
Recording ID: {segment.id}
Camera: {segment.camera_id}
Tenant: {segment.tenant_id}
Period: {segment.started_at.isoformat()} → {segment.ended_at.isoformat()}
Duration: {segment.duration_seconds}s
File: {segment.file_path}
Stored SHA-256: {segment.sha256_hash.value if segment.sha256_hash else 'N/A'}
Current SHA-256: {current_hash.value}
Integrity Verified: {'YES' if is_verified else 'NO - VIOLATION DETECTED'}
Report Generated: {DT.now(timezone.utc).isoformat()}
"""
        zf.writestr('integrity_report.txt', report)

        # 5. checksum.sha256
        zf.writestr('checksum.sha256', f"{current_hash.value}  recording.mp4\n")

    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()

    # Assinar com HMAC-SHA256
    signature = sign_webhook_payload(zip_bytes, "forensic-export")

    # Salvar ZIP em disco
    import tempfile
    forensic_dir = os.environ.get("FORENSIC_EXPORT_PATH", os.path.join(tempfile.gettempdir(), "forensic_exports"))
    os.makedirs(forensic_dir, exist_ok=True)

    zip_filename = f"forensic_{recording_id}_{DT.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join(forensic_dir, zip_filename)

    with open(zip_path, "wb") as f:
        f.write(zip_bytes)

    # Persistir custody_chain entry
    custody_entry = {
        "action": "recording.exported_forensic",
        "timestamp": DT.now(timezone.utc).isoformat(),
        "actor": str(claims.user_id),
        "user_email": getattr(claims, "email", None),
        "file_path": zip_path,
        "zip_size_bytes": len(zip_bytes),
        "hmac_signature": signature,
    }
    current_chain = getattr(segment, "custody_chain", []) or []
    current_chain.append(custody_entry)
    await svc._segments.update_integrity(
        segment_id=recording_id,
        tenant_id=claims.tenant_id,
        custody_chain=current_chain,
    )

    logger.info("Export forense salvo: %s (%d bytes)", zip_path, len(zip_bytes))

    return {
        "recording_id": recording_id,
        "exported_at": DT.now(timezone.utc).isoformat(),
        "exported_by": str(claims.user_id),
        "file_path": zip_path,
        "download_url": f"/api/v1/recordings/forensic/{recording_id}/download",
        "zip_size_bytes": len(zip_bytes),
        "sha256_hash": current_hash.value,
        "hmac_signature": signature,
        "integrity_verified": is_verified,
    }
