"""Rotas HTTP do bounded context de streaming."""
from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, status

from vms.core.deps import DbSession
from vms.streaming.repository import StreamSessionRepository
from vms.streaming.schemas import PublishAuthRequest, PublishAuthResponse
from vms.streaming.service import StreamingService

logger = logging.getLogger(__name__)
router = APIRouter()


def _streaming_svc(db: DbSession) -> StreamingService:
    """Constrói StreamingService com repositório."""
    return StreamingService(StreamSessionRepository(db))


@router.post(
    "/streaming/publish-auth",
    response_model=PublishAuthResponse,
    summary="Autenticação de publicação MediaMTX",
    tags=["streaming"],
)
async def publish_auth(body: PublishAuthRequest, db: DbSession) -> PublishAuthResponse:
    """
    MediaMTX chama antes de aceitar publisher.

    Verifica se o path é válido e o token corresponde a um agent autorizado.
    """
    token = _extract_token(body.query)
    svc = _streaming_svc(db)
    allowed = await svc.verify_publish_token(body.path, token)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Publicação não autorizada",
        )

    return PublishAuthResponse(ok=True)


def _extract_token(query: str) -> str:
    """Extrai token da query string do MediaMTX."""
    params = parse_qs(query)
    tokens = params.get("token", [])
    return tokens[0] if tokens else ""
