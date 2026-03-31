"""Rotas HTTP do bounded context de câmeras e agents."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from vms.cameras.repository import AgentRepository, CameraRepository
from vms.cameras.schemas import (
    AgentConfigResponse,
    AgentResponse,
    CameraConfigItem,
    CameraResponse,
    CreateAgentRequest,
    CreateAgentResponse,
    CreateCameraRequest,
    HeartbeatRequest,
    UpdateCameraRequest,
)
from vms.cameras.service import AgentService, CameraService
from vms.core.deps import ApiKeyHeader, CurrentUser, DbSession
from vms.iam.repository import ApiKeyRepository
from vms.iam.service import ApiKeyService

router = APIRouter()


# ─── Factories ────────────────────────────────────────────────────────────────

def _camera_svc(db: AsyncSession) -> CameraService:
    """Constrói CameraService com repositório."""
    return CameraService(CameraRepository(db))


def _agent_svc(db: AsyncSession) -> AgentService:
    """Constrói AgentService com dependências."""
    return AgentService(
        AgentRepository(db),
        CameraRepository(db),
        ApiKeyService(ApiKeyRepository(db)),
    )


# ─── Câmeras ──────────────────────────────────────────────────────────────────

@router.get(
    "/cameras",
    response_model=list[CameraResponse],
    summary="Listar câmeras",
    tags=["cameras"],
)
async def list_cameras(
    claims: CurrentUser,
    db: DbSession,
    is_online: bool | None = None,
) -> list[CameraResponse]:
    """Lista câmeras do tenant autenticado."""
    svc = _camera_svc(db)
    cameras = await svc.list_cameras(claims.tenant_id, is_online=is_online)
    return [CameraResponse.model_validate(c) for c in cameras]


@router.post(
    "/cameras",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar câmera",
    tags=["cameras"],
)
async def create_camera(
    body: CreateCameraRequest,
    claims: CurrentUser,
    db: DbSession,
) -> CameraResponse:
    """Cria câmera e registra path no MediaMTX."""
    svc = _camera_svc(db)
    camera = await svc.create_camera(
        tenant_id=claims.tenant_id,
        name=body.name,
        rtsp_url=body.rtsp_url,
        manufacturer=body.manufacturer,
        location=body.location,
        retention_days=body.retention_days,
        agent_id=body.agent_id,
    )
    return CameraResponse.model_validate(camera)


@router.get(
    "/cameras/{camera_id}",
    response_model=CameraResponse,
    summary="Buscar câmera",
    tags=["cameras"],
)
async def get_camera(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> CameraResponse:
    """Retorna câmera pelo ID."""
    svc = _camera_svc(db)
    camera = await svc.get_camera(camera_id, claims.tenant_id)
    return CameraResponse.model_validate(camera)


@router.patch(
    "/cameras/{camera_id}",
    response_model=CameraResponse,
    summary="Atualizar câmera",
    tags=["cameras"],
)
async def update_camera(
    camera_id: str,
    body: UpdateCameraRequest,
    claims: CurrentUser,
    db: DbSession,
) -> CameraResponse:
    """Atualiza campos da câmera."""
    svc = _camera_svc(db)
    camera = await svc.update_camera(
        camera_id=camera_id,
        tenant_id=claims.tenant_id,
        name=body.name,
        rtsp_url=body.rtsp_url,
        manufacturer=body.manufacturer,
        location=body.location,
        retention_days=body.retention_days,
        agent_id=body.agent_id,
        is_active=body.is_active,
    )
    return CameraResponse.model_validate(camera)


@router.delete(
    "/cameras/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover câmera",
    tags=["cameras"],
)
async def delete_camera(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> None:
    """Remove câmera e seu path no MediaMTX (best-effort)."""
    svc = _camera_svc(db)
    await svc.delete_camera(camera_id, claims.tenant_id)


# ─── Agents ───────────────────────────────────────────────────────────────────

@router.get(
    "/agents",
    response_model=list[AgentResponse],
    summary="Listar agents",
    tags=["agents"],
)
async def list_agents(
    claims: CurrentUser,
    db: DbSession,
) -> list[AgentResponse]:
    """Lista agents do tenant autenticado."""
    svc = _agent_svc(db)
    agents = await svc.list_agents(claims.tenant_id)
    return [AgentResponse.model_validate(a) for a in agents]


@router.post(
    "/agents",
    response_model=CreateAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar agent",
    tags=["agents"],
)
async def create_agent(
    body: CreateAgentRequest,
    claims: CurrentUser,
    db: DbSession,
) -> CreateAgentResponse:
    """Cria agent e emite API key (exibida uma única vez)."""
    svc = _agent_svc(db)
    agent, plain_key = await svc.create_agent(claims.tenant_id, body.name)
    return CreateAgentResponse(
        id=agent.id,
        name=agent.name,
        status=agent.status.value,
        last_heartbeat_at=agent.last_heartbeat_at,
        version=agent.version,
        streams_running=agent.streams_running,
        streams_failed=agent.streams_failed,
        created_at=agent.created_at,
        api_key=plain_key,
    )


@router.get(
    "/agents/me/config",
    response_model=AgentConfigResponse,
    summary="Configuração do agent autenticado",
    tags=["agents"],
)
async def get_agent_config(
    api_key: ApiKeyHeader,
    db: DbSession,
) -> AgentConfigResponse:
    """Retorna configuração de câmeras para o agent autenticado via API key."""
    from vms.iam.service import AuthService
    from vms.iam.repository import ApiKeyRepository as IamApiKeyRepo

    auth_svc = AuthService(
        user_repo=None,  # type: ignore[arg-type]
        api_key_repo=IamApiKeyRepo(db),
    )
    key_entity = await auth_svc.authenticate_api_key(api_key)
    svc = _agent_svc(db)
    agent, configs = await svc.get_agent_config(key_entity.owner_id, key_entity.tenant_id)
    return AgentConfigResponse(
        agent_id=agent.id,
        cameras=[
            CameraConfigItem(
                id=c.id,
                name=c.name,
                rtsp_url=c.rtsp_url,
                rtmp_push_url=c.rtmp_push_url,
                enabled=c.enabled,
            )
            for c in configs
        ],
    )


@router.post(
    "/agents/me/heartbeat",
    response_model=AgentResponse,
    summary="Heartbeat do agent autenticado",
    tags=["agents"],
)
async def agent_heartbeat(
    body: HeartbeatRequest,
    api_key: ApiKeyHeader,
    db: DbSession,
) -> AgentResponse:
    """Registra heartbeat do agent e atualiza status para online."""
    from vms.iam.service import AuthService
    from vms.iam.repository import ApiKeyRepository as IamApiKeyRepo

    auth_svc = AuthService(
        user_repo=None,  # type: ignore[arg-type]
        api_key_repo=IamApiKeyRepo(db),
    )
    key_entity = await auth_svc.authenticate_api_key(api_key)
    svc = _agent_svc(db)
    agent = await svc.register_heartbeat(
        agent_id=key_entity.owner_id,
        tenant_id=key_entity.tenant_id,
        version=body.version,
        streams_running=body.streams_running,
        streams_failed=body.streams_failed,
    )
    return AgentResponse.model_validate(agent)


@router.get(
    "/agents/{agent_id}",
    response_model=AgentResponse,
    summary="Buscar agent",
    tags=["agents"],
)
async def get_agent(
    agent_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> AgentResponse:
    """Retorna agent pelo ID."""
    svc = _agent_svc(db)
    agent = await svc.get_agent(agent_id, claims.tenant_id)
    return AgentResponse.model_validate(agent)


@router.delete(
    "/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover agent",
    tags=["agents"],
)
async def delete_agent(
    agent_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> None:
    """Remove agent e revoga sua API key."""
    svc = _agent_svc(db)
    await svc.delete_agent(agent_id, claims.tenant_id)
