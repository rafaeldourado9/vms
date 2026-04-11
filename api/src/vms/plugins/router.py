"""Rotas do contrato público de plugins — acesso por API key."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from vms.cameras.repository import CameraRepository
from vms.core.deps import ApiKeyHeader, DbSession
from vms.core.exceptions import AuthenticationError, NotFoundError
from vms.iam.repository import ApiKeyRepository
from vms.iam.service import AuthService
from vms.plugins.schemas import (
    PluginCameraResponse,
    PluginEventRequest,
    PluginEventResponse,
    StreamTokenResponse,
)
from vms.plugins.service import PluginService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["plugins"])


# ─── Dependência de autenticação por API key ──────────────────────────────────

async def _resolve_plugin_tenant(api_key: ApiKeyHeader, db: DbSession) -> str:
    """Autentica API key e retorna tenant_id associado."""
    auth_svc = AuthService(
        user_repo=None,  # type: ignore[arg-type]
        api_key_repo=ApiKeyRepository(db),
    )
    try:
        key_entity = await auth_svc.authenticate_api_key(api_key)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou revogada",
        ) from exc
    return key_entity.tenant_id


def _plugin_svc(db: AsyncSession) -> PluginService:
    return PluginService(CameraRepository(db))


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/plugins/cameras",
    response_model=list[PluginCameraResponse],
    summary="Câmeras disponíveis para o plugin",
)
async def list_plugin_cameras(api_key: ApiKeyHeader, db: DbSession) -> list[PluginCameraResponse]:
    """
    Lista câmeras ativas do tenant associado à API key.

    O plugin usa este endpoint para descobrir quais streams processar.
    """
    tenant_id = await _resolve_plugin_tenant(api_key, db)
    cameras = await _plugin_svc(db).list_cameras(tenant_id)
    return [
        PluginCameraResponse(
            id=c.id,
            name=c.name,
            manufacturer=c.manufacturer.value,
            stream_protocol=c.stream_protocol.value,
            is_online=c.is_online,
            mediamtx_path=c.mediamtx_path,
            location=c.location,
        )
        for c in cameras
        if c.is_active
    ]


@router.get(
    "/plugins/stream-token",
    response_model=StreamTokenResponse,
    summary="Token de acesso ao stream RTSP",
)
async def get_stream_token(
    camera_id: str,
    api_key: ApiKeyHeader,
    db: DbSession,
    request: Request,
) -> StreamTokenResponse:
    """
    Gera token JWT de curta duração para o plugin acessar o stream RTSP no MediaMTX.

    O plugin monta a URL como: rtsp://<token>@<host>:8554/<mediamtx_path>
    O token expira no mesmo intervalo que os access tokens de usuário.
    """
    tenant_id = await _resolve_plugin_tenant(api_key, db)
    mediamtx_host = request.headers.get("X-MediaMTX-Host", "mediamtx")

    try:
        result = await _plugin_svc(db).get_stream_token(camera_id, tenant_id, mediamtx_host)
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StreamTokenResponse(**result)


@router.post(
    "/plugins/events",
    response_model=PluginEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingestão de evento detectado pelo plugin",
)
async def ingest_plugin_event(
    body: PluginEventRequest,
    api_key: ApiKeyHeader,
    db: DbSession,
) -> PluginEventResponse:
    """
    Recebe evento detectado pelo plugin e persiste como VmsEvent.

    O `event_type` é livre — convenção recomendada: `<plugin>.<acao>`.
    Exemplos: `intrusion.detected`, `lpr.detected`, `people.count`.

    O `payload` aceita qualquer estrutura — o VMS não valida o conteúdo.
    """
    tenant_id = await _resolve_plugin_tenant(api_key, db)
    event_id = await _plugin_svc(db).ingest_event(
        db=db,
        tenant_id=tenant_id,
        camera_id=body.camera_id,
        event_type=body.event_type,
        confidence=body.confidence,
        occurred_at=body.occurred_at,
        payload=body.payload,
    )
    return PluginEventResponse(id=event_id)
