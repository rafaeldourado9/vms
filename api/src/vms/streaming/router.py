"""Rotas HTTP do bounded context de streaming."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request, status

from vms.cameras.repository import CameraRepository
from vms.shared.api.dependencies import DbSession
from vms.iam.repository import ApiKeyRepository
from vms.streaming.ports import StreamAuthPort, StreamCameraPort
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
    """Constrói StreamingService com ports de auth."""
    camera_repo = CameraRepository(db)
    api_key_repo = ApiKeyRepository(db)

    # Adapter: implementa StreamCameraPort usando CameraRepository
    class _CameraPortAdapter(StreamCameraPort):
        async def get_by_id(self, camera_id, tenant_id):
            return await camera_repo.get_by_id(camera_id, tenant_id)
        async def get_by_stream_key(self, stream_key):
            return await camera_repo.get_by_stream_key(stream_key)
        async def get_by_mediamtx_path(self, mediamtx_path):
            return await camera_repo.get_by_mediamtx_path(mediamtx_path)

    # Adapter: implementa StreamAuthPort usando ApiKeyRepository + security
    class _AuthPortAdapter(StreamAuthPort):
        async def verify_api_key(self, api_key):
            from vms.infrastructure.security import extract_key_prefix, verify_api_key
            prefix = extract_key_prefix(api_key)
            key_obj = await api_key_repo.get_by_prefix(prefix)
            if key_obj and key_obj.is_active and verify_api_key(api_key, key_obj.key_hash):
                await api_key_repo.update_last_used(key_obj.id)
                return key_obj.owner_id
            return None
        async def decode_viewer_token(self, token):
            from vms.infrastructure.security import decode_token
            return decode_token(token)

    return StreamingService(
        StreamSessionRepository(db),
        camera_port=_CameraPortAdapter(),
        auth_port=_AuthPortAdapter(),
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
