"""Rotas HTTP do bounded context de streaming."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, status

from vms.cameras.repository import CameraRepository
from vms.core.deps import DbSession
from vms.iam.repository import ApiKeyRepository
from vms.streaming.repository import StreamSessionRepository
from vms.streaming.schemas import PublishAuthRequest, PublishAuthResponse, ReadAuthRequest
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
async def publish_auth(body: PublishAuthRequest, db: DbSession) -> PublishAuthResponse:
    """
    MediaMTX chama antes de aceitar publisher ou viewer (authHTTPAddress).

    Despacha para verify_viewer_token quando action=="read",
    caso contrário valida stream key (câmeras RTMP push) ou API key (agents).
    """
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


@router.get(
    "/streaming/auth-check",
    status_code=status.HTTP_200_OK,
    summary="Nginx auth_request — valida viewer token",
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
