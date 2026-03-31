"""Rotas HTTP do bounded context de configuração de analytics."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from vms.analytics_config.repository import ROIRepository
from vms.analytics_config.schemas import (
    CreateROIRequest,
    ROIForAnalytics,
    ROIResponse,
    UpdateROIRequest,
)
from vms.analytics_config.service import ROIService
from vms.core.config import get_settings
from vms.core.deps import CurrentUser, DbSession

router = APIRouter()
internal_router = APIRouter()


def _svc(db: DbSession) -> ROIService:
    """Constrói ROIService com repositório injetado."""
    return ROIService(ROIRepository(db))


def _roi_to_response(roi: object) -> ROIResponse:
    """Converte entidade de domínio para schema de resposta."""
    from vms.analytics_config.domain import RegionOfInterest
    r: RegionOfInterest = roi  # type: ignore[assignment]
    return ROIResponse(
        id=r.id,
        tenant_id=r.tenant_id,
        camera_id=r.camera_id,
        name=r.name,
        ia_type=r.ia_type,
        polygon_points=r.polygon_points,
        config=r.config,
        is_active=r.is_active,
        created_at=r.created_at,
    )


# ─── Endpoints públicos (requerem JWT) ────────────────────────────────────────

@router.get(
    "/analytics/rois",
    response_model=list[ROIResponse],
    summary="Listar ROIs do tenant",
    tags=["analytics-config"],
)
async def list_rois(claims: CurrentUser, db: DbSession) -> list[ROIResponse]:
    """Lista todas as ROIs ativas do tenant autenticado."""
    rois = await _svc(db).list_rois(claims.tenant_id)
    return [_roi_to_response(r) for r in rois]


@router.post(
    "/analytics/rois",
    response_model=ROIResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar ROI",
    tags=["analytics-config"],
)
async def create_roi(
    body: CreateROIRequest,
    claims: CurrentUser,
    db: DbSession,
) -> ROIResponse:
    """Cria nova Região de Interesse vinculada a uma câmera."""
    roi = await _svc(db).create_roi(
        tenant_id=claims.tenant_id,
        camera_id=body.camera_id,
        name=body.name,
        ia_type=body.ia_type,
        polygon_points=body.polygon_points,
        config=body.config,
        is_active=body.is_active,
    )
    return _roi_to_response(roi)


@router.get(
    "/analytics/rois/{roi_id}",
    response_model=ROIResponse,
    summary="Buscar ROI",
    tags=["analytics-config"],
)
async def get_roi(
    roi_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> ROIResponse:
    """Retorna ROI pelo ID."""
    roi = await _svc(db).get_roi(roi_id, claims.tenant_id)
    return _roi_to_response(roi)


@router.patch(
    "/analytics/rois/{roi_id}",
    response_model=ROIResponse,
    summary="Atualizar ROI",
    tags=["analytics-config"],
)
async def update_roi(
    roi_id: str,
    body: UpdateROIRequest,
    claims: CurrentUser,
    db: DbSession,
) -> ROIResponse:
    """Atualiza campos de uma ROI existente (PATCH parcial)."""
    roi = await _svc(db).update_roi(
        roi_id=roi_id,
        tenant_id=claims.tenant_id,
        name=body.name,
        ia_type=body.ia_type,
        polygon_points=body.polygon_points,
        config=body.config,
        is_active=body.is_active,
    )
    return _roi_to_response(roi)


@router.delete(
    "/analytics/rois/{roi_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remover ROI",
    tags=["analytics-config"],
)
async def delete_roi(
    roi_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> None:
    """Remove ROI permanentemente."""
    await _svc(db).delete_roi(roi_id, claims.tenant_id)


# ─── Endpoint interno (requer Analytics API key) ──────────────────────────────

@internal_router.get(
    "/internal/cameras/{camera_id}/rois",
    response_model=list[ROIForAnalytics],
    summary="ROIs de câmera — uso interno do analytics_service",
    tags=["internal"],
)
async def get_camera_rois_internal(
    camera_id: str,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> list[ROIForAnalytics]:
    """
    Retorna ROIs ativas de uma câmera para o analytics_service.

    Requer header Authorization: ApiKey <analytics_api_key>.
    Este endpoint é chamado exclusivamente pelo analytics_service.
    """
    settings = get_settings()
    expected = f"ApiKey {settings.analytics_api_key}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Analytics API key inválida ou ausente",
        )

    repo = ROIRepository(db)
    # Busca ROIs de qualquer tenant para esta câmera — o analytics_service
    # não conhece o tenant, apenas o camera_id extraído do path MediaMTX.
    from sqlalchemy import select
    from vms.analytics_config.models import RegionOfInterestModel

    stmt = select(RegionOfInterestModel).where(
        RegionOfInterestModel.camera_id == camera_id,
        RegionOfInterestModel.is_active.is_(True),
    )
    result = await db.scalars(stmt)
    models = result.all()

    return [
        ROIForAnalytics(
            id=m.id,
            camera_id=m.camera_id,
            name=m.name,
            ia_type=m.ia_type,
            polygon_points=m.polygon_points,
            config=m.config,
        )
        for m in models
    ]
