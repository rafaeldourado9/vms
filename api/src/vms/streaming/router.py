"""Rotas HTTP do bounded context de streaming."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request, status

from vms.cameras.repository import CameraRepository
from vms.core.deps import DbSession
from vms.iam.repository import ApiKeyRepository
from vms.streaming.repository import StreamSessionRepository
from vms.streaming.schemas import (
    AnalyticsAuthRequest,
    PublishAuthRequest,
    PublishAuthResponse,
    ReadAuthRequest,
)
from vms.streaming.service import StreamingService

logger = logging.getLogger(__name__)
router = APIRouter()


def _streaming_svc(db: DbSession) -> StreamingService:
    """Constrói StreamingService com repositórios de auth."""
    return StreamingService(
        StreamSessionRepository(db),
        camera_repo=CameraRepository(db),
        api_key_repo=ApiKeyRepository(db),
    )


@router.post(
    "/streaming/publish-auth",
    response_model=PublishAuthResponse,
    summary="Autenticação de publicação MediaMTX",
    tags=["streaming"],
)
async def publish_auth(
    body: PublishAuthRequest,
    db: DbSession,
    request: Request,
) -> PublishAuthResponse:
    """
    MediaMTX chama antes de aceitar publisher ou viewer (authHTTPAddress).

    Se o request vem do analytics service (header X-Analytics-Service),
    usa autenticação simplificada (apenas verifica se câmera existe e está online).

    Caso contrário:
    - Despacha para verify_viewer_token quando action=="read"
    - Valida stream key (câmeras RTMP push) ou API key (agents)
    """
    # Detectar se é request do analytics service
    analytics_header = request.headers.get("X-Analytics-Service", "")
    if analytics_header and body.action == "read":
        # Autenticação simplificada para analytics
        camera_repo = CameraRepository(db)
        camera = await camera_repo.get_by_mediamtx_path(body.path)

        if not camera or not camera.is_online:
            logger.debug(
                "Analytics auth rejeitado: path=%s, online=%s",
                body.path,
                camera.is_online if camera else "N/A",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Câmera não encontrada ou offline",
            )

        return PublishAuthResponse(ok=True)

    # Fluxo normal (não-analytics)
    token = _extract_token(body.query)
    svc = _streaming_svc(db)

    if body.action == "read":
        allowed = await svc.verify_viewer_token(token, body.path)
    else:
        allowed = await svc.verify_publish_token(body.path, token)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado",
        )

    return PublishAuthResponse(ok=True)


@router.post(
    "/streaming/read-auth",
    response_model=PublishAuthResponse,
    summary="Autenticação de leitura MediaMTX",
    tags=["streaming"],
)
async def read_auth(body: ReadAuthRequest, db: DbSession) -> PublishAuthResponse:
    """
    MediaMTX chama antes de aceitar viewer (HLS/WebRTC).

    Valida ViewerToken JWT com claims camera_id e tenant_id.
    """
    token = _extract_token(body.query)
    svc = _streaming_svc(db)
    allowed = await svc.verify_viewer_token(token, body.path)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Visualização não autorizada",
        )

    return PublishAuthResponse(ok=True)


@router.post(
    "/streaming/analytics-auth",
    response_model=PublishAuthResponse,
    summary="Autenticação de leitura para Analytics Service",
    tags=["streaming"],
)
async def analytics_auth(body: AnalyticsAuthRequest, db: DbSession) -> PublishAuthResponse:
    """
    MediaMTX chama quando o analytics service tenta ler um stream RTSP.

    Diferente do read_auth, este endpoint **não valida token** — apenas verifica:
    1. Se o path existe (câmera provisionada)
    2. Se a câmera está online e ativa

    Isso permite que o analytics acesse streams diretamente do MediaMTX
    sem precisar de tokens JWT, simplificando a arquitetura.
    """
    camera_repo = CameraRepository(db)
    camera = await camera_repo.get_by_mediamtx_path(body.path)

    if not camera or not camera.is_online:
        logger.debug("Analytics auth rejeitado: path=%s, camera=%s", body.path, camera is not None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Câmera não encontrada ou offline",
        )

    return PublishAuthResponse(ok=True)


@router.get(
    "/streaming/auth-check",
    status_code=status.HTTP_200_OK,
    summary="Nginx auth_request — valida viewer token para HLS/WebRTC",
    tags=["streaming"],
    include_in_schema=False,
)
async def streaming_auth_check(
    token: str = Query(""),
    path: str = Query(""),
    db: DbSession = None,  # type: ignore[assignment]
) -> dict[str, str]:
    """
    Chamado pelo nginx via `auth_request` para /hls/ e /webrtc/.
    Retorna 200 se token válido, 401 caso contrário.
    """
    svc = _streaming_svc(db)
    allowed = await svc.verify_viewer_token(token, path)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de visualização inválido ou expirado",
        )
    return {"ok": "true"}


def _extract_token(query: str) -> str:
    """Extrai token da query string do MediaMTX (suporta ?token= e ?key=)."""
    params = parse_qs(query)
    values = params.get("token") or params.get("key") or []
    return values[0] if values else ""
