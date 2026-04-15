"""Rotas HTTP do serviço VOD."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from vms.shared.api.dependencies import CurrentUser, DbSession
from vms.recordings.repository import RecordingSegmentRepository
from vms.vod.repository import VODRepository
from vms.vod.schemas import CreateVODStreamRequest, VODPlaylistURL, VODStreamResponse
from vms.vod.service import VODService  # noqa: F401 — usado nas closures de background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vod", tags=["vod"])


def _vod_svc(db: DbSession) -> VODService:
    """Constrói VODService com repositório."""
    return VODService(VODRepository(db))


@router.post(
    "/streams",
    response_model=VODStreamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar stream VOD",
)
async def create_vod_stream(
    body: CreateVODStreamRequest,
    claims: CurrentUser,
    db: DbSession,
) -> VODStreamResponse:
    """Cria stream VOD a partir de segmentos de gravação.

    O processamento HLS ocorre em background. Poll o status via GET.
    """
    # Busca segmentos do banco
    repo = RecordingSegmentRepository(db)
    segments = []
    for seg_id in body.segment_ids:
        seg = await repo.get_by_id(seg_id, claims.tenant_id)
        if not seg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Segmento não encontrado: {seg_id}",
            )
        segments.append(seg)

    if not segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum segmento válido fornecido",
        )

    # Ordena por timestamp
    segments.sort(key=lambda s: s.started_at)

    # Cria stream VOD
    svc = _vod_svc(db)
    vod = await svc.create_vod_stream(
        stream_id=str(uuid.uuid4()),
        tenant_id=claims.tenant_id,
        camera_id=body.camera_id,
        segments=[s.file_path for s in segments],
        started_at=body.starts_at,
        ended_at=body.ends_at,
    )

    # Gera playlist em background com sessão própria (não reutiliza sessão do request)
    import asyncio
    from vms.infrastructure.database import get_session_factory
    from vms.vod.repository import VODRepository as _VODRepo

    async def _generate_in_background(vod_snapshot):
        factory = get_session_factory()
        async with factory() as bg_session:
            bg_svc = VODService(_VODRepo(bg_session))
            try:
                await bg_svc.generate_hls_playlist(vod_snapshot)
            except Exception:
                logger.warning("Falha ao gerar VOD %s", vod_snapshot.id)
            finally:
                await bg_session.commit()

    asyncio.create_task(_generate_in_background(vod))

    return VODStreamResponse.model_validate(vod)


@router.get(
    "/streams/{stream_id}",
    response_model=VODStreamResponse,
    summary="Status do stream VOD",
)
async def get_vod_stream(
    stream_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> VODStreamResponse:
    """Retorna status do stream VOD (para polling)."""
    svc = _vod_svc(db)
    vod = await svc._repo.get_by_id(stream_id, claims.tenant_id)
    if not vod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream VOD não encontrado")

    return VODStreamResponse.model_validate(vod)


@router.get(
    "/streams/{stream_id}/playlist",
    response_model=VODPlaylistURL,
    summary="URL da playlist HLS",
)
async def get_vod_playlist(
    stream_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> VODPlaylistURL:
    """Retorna URL da playlist HLS para streaming."""
    svc = _vod_svc(db)
    vod = await svc._repo.get_by_id(stream_id, claims.tenant_id)
    if not vod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream VOD não encontrado")

    if vod.status == "pending":
        # Inicia geração se ainda não começou, com sessão própria
        import asyncio
        from vms.infrastructure.database import get_session_factory
        from vms.vod.repository import VODRepository as _VODRepo2

        async def _gen_bg(vod_snap):
            factory = get_session_factory()
            async with factory() as bg_session:
                bg_svc = VODService(_VODRepo2(bg_session))
                try:
                    await bg_svc.generate_hls_playlist(vod_snap)
                except Exception:
                    logger.warning("Falha ao gerar VOD %s", vod_snap.id)
                finally:
                    await bg_session.commit()

        asyncio.create_task(_gen_bg(vod))
        return VODPlaylistURL(playlist_url="", status="generating", stream_id=stream_id)

    if vod.status == "generating":
        return VODPlaylistURL(playlist_url="", status="generating", stream_id=stream_id)

    if vod.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao gerar HLS: {vod.error}",
        )

    # Retorna URL pública do playlist
    # Nginx vai servir este arquivo
    playlist_url = f"/vod-streams/{claims.tenant_id}/{vod.camera_id}/{stream_id}/playlist.m3u8"
    return VODPlaylistURL(playlist_url=playlist_url, status="ready", stream_id=stream_id)


@router.get(
    "/playlists/{tenant_id}/{camera_id}/{stream_id}/{filename}",
    summary="Servir arquivo HLS (.m3u8 ou .ts)",
)
async def serve_hls_file(
    tenant_id: str,
    camera_id: str,
    stream_id: str,
    filename: str,
    claims: CurrentUser,
    db: DbSession,
) -> FileResponse:
    """Serve arquivos de playlist HLS ou segmentos .ts."""
    if not filename.endswith((".m3u8", ".ts")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo inválido")

    # Path do arquivo
    import os
    from pathlib import Path

    base_dir = Path("/tmp/vod")  # Deve corresponder ao output_dir do VODService
    file_path = base_dir / tenant_id / camera_id / stream_id / filename

    # Verifica se arquivo existe
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado")

    # Verifica path traversal
    if not str(file_path.resolve()).startswith(str(base_dir.resolve())):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    # Determina content-type
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/MP2T"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get(
    "/streams",
    response_model=list[VODStreamResponse],
    summary="Listar streams VOD",
)
async def list_vod_streams(
    claims: CurrentUser,
    db: DbSession,
    camera_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None),
) -> list[VODStreamResponse]:
    """Lista streams VOD do tenant."""
    from sqlalchemy import select
    from vms.vod.models import VODStreamModel

    stmt = select(VODStreamModel).where(VODStreamModel.tenant_id == claims.tenant_id)

    if camera_id:
        stmt = stmt.where(VODStreamModel.camera_id == camera_id)
    if status_filter:
        stmt = stmt.where(VODStreamModel.status == status_filter)

    stmt = stmt.order_by(VODStreamModel.created_at.desc()).limit(50)

    result = await db.scalars(stmt)
    return [VODStreamResponse.model_validate(m) for m in result.all()]


@router.delete(
    "/streams/{stream_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover stream VOD",
)
async def delete_vod_stream(
    stream_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> None:
    """Remove stream VOD e arquivos associados."""
    svc = _vod_svc(db)
    vod = await svc._repo.get_by_id(stream_id, claims.tenant_id)
    if not vod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream VOD não encontrado")

    await svc._repo.cleanup_expired(claims.tenant_id, vod.created_at)

    # Remove arquivos físicos
    import shutil
    from pathlib import Path

    stream_dir = Path("/tmp/vod") / claims.tenant_id / vod.camera_id / stream_id
    if stream_dir.exists():
        shutil.rmtree(stream_dir, ignore_errors=True)
