"""Rotas HTTP do bounded context PTZ."""
from __future__ import annotations

from fastapi import APIRouter, status

from vms.cameras.repository import CameraRepository
from vms.core.deps import CurrentUser, DbSession
from vms.ptz.domain import PtzVector
from vms.ptz.schemas import (
    PtzActionResponse,
    PtzMoveRequest,
    PtzPresetResponse,
    PtzPresetsResponse,
    SavePresetRequest,
)
from vms.ptz.service import PtzService

router = APIRouter(tags=["ptz"])


def _ptz_svc(db) -> PtzService:
    return PtzService(CameraRepository(db))


@router.post(
    "/cameras/{camera_id}/ptz/move",
    response_model=PtzActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Mover câmera PTZ (contínuo)",
)
async def ptz_move(
    camera_id: str,
    body: PtzMoveRequest,
    claims: CurrentUser,
    db: DbSession,
) -> PtzActionResponse:
    """
    Inicia movimento contínuo PTZ.

    Valores de -1.0 a 1.0 para pan/tilt e 0.0 a 1.0 para zoom.
    O movimento para automaticamente após `timeout_seconds` ou quando
    `POST /ptz/stop` for chamado.
    """
    svc = _ptz_svc(db)
    await svc.move(
        camera_id=camera_id,
        tenant_id=claims.tenant_id,
        velocity=PtzVector(pan=body.pan, tilt=body.tilt, zoom=body.zoom),
        timeout_seconds=body.timeout_seconds,
    )
    return PtzActionResponse(ok=True, message="Movimento iniciado")


@router.post(
    "/cameras/{camera_id}/ptz/stop",
    response_model=PtzActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Parar movimento PTZ",
)
async def ptz_stop(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> PtzActionResponse:
    """Para qualquer movimento PTZ (pan, tilt e zoom) em curso."""
    svc = _ptz_svc(db)
    await svc.stop(camera_id=camera_id, tenant_id=claims.tenant_id)
    return PtzActionResponse(ok=True, message="Movimento parado")


@router.get(
    "/cameras/{camera_id}/ptz/presets",
    response_model=PtzPresetsResponse,
    summary="Listar presets PTZ",
)
async def list_ptz_presets(
    camera_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> PtzPresetsResponse:
    """Lista os presets PTZ salvos na câmera."""
    svc = _ptz_svc(db)
    presets = await svc.get_presets(camera_id=camera_id, tenant_id=claims.tenant_id)
    return PtzPresetsResponse(
        presets=[PtzPresetResponse(token=p.token, name=p.name) for p in presets]
    )


@router.post(
    "/cameras/{camera_id}/ptz/presets/{preset_token}/goto",
    response_model=PtzActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Ir para preset PTZ",
)
async def goto_ptz_preset(
    camera_id: str,
    preset_token: str,
    claims: CurrentUser,
    db: DbSession,
) -> PtzActionResponse:
    """Move câmera para a posição memorizada no preset informado."""
    svc = _ptz_svc(db)
    await svc.goto_preset(
        camera_id=camera_id,
        tenant_id=claims.tenant_id,
        preset_token=preset_token,
    )
    return PtzActionResponse(ok=True, message=f"Movendo para preset '{preset_token}'")


@router.post(
    "/cameras/{camera_id}/ptz/presets/{preset_token}/save",
    response_model=PtzPresetResponse,
    status_code=status.HTTP_200_OK,
    summary="Salvar posição atual como preset PTZ",
)
async def save_ptz_preset(
    camera_id: str,
    preset_token: str,
    body: SavePresetRequest,
    claims: CurrentUser,
    db: DbSession,
) -> PtzPresetResponse:
    """
    Salva a posição atual da câmera como preset.

    Se `preset_token` já existir, sobrescreve a posição.
    Use `"new"` para criar um novo preset.
    """
    svc = _ptz_svc(db)
    token = preset_token if preset_token != "new" else None
    preset = await svc.save_preset(
        camera_id=camera_id,
        tenant_id=claims.tenant_id,
        preset_name=body.name,
        preset_token=token,
    )
    return PtzPresetResponse(token=preset.token, name=preset.name)
