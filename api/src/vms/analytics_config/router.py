"""Rotas HTTP do bounded context de configuração de analytics."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, status

from vms.analytics_config.repository import ROIRepository
from vms.analytics_config.schemas import (
    AnalyticsIngestRequest,
    AnalyticsSummaryResponse,
    CreateROIRequest,
    ROIEventSummary,
    ROIForAnalytics,
    ROIResponse,
    UpdateROIRequest,
)
from vms.analytics_config.service import ROIService
from vms.core.config import get_settings
from vms.core.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

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


@router.get(
    "/analytics/rois/{roi_id}/events",
    summary="Eventos gerados por esta ROI",
    tags=["analytics-config"],
)
async def get_roi_events(
    roi_id: str,
    claims: CurrentUser,
    db: DbSession,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Lista eventos VmsEvent gerados por uma ROI específica (filtrado por roi_id no payload)."""
    from sqlalchemy import func, select
    from vms.events.models import VmsEventModel

    offset = (page - 1) * page_size
    base = select(VmsEventModel).where(
        VmsEventModel.tenant_id == claims.tenant_id,
        VmsEventModel.payload["roi_id"].as_string() == roi_id,
    )
    if started_after:
        base = base.where(VmsEventModel.occurred_at >= started_after)
    if started_before:
        base = base.where(VmsEventModel.occurred_at <= started_before)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = await db.scalar(count_stmt) or 0

    stmt = base.order_by(VmsEventModel.occurred_at.desc()).limit(page_size).offset(offset)
    result = await db.scalars(stmt)
    events = result.all()

    return {
        "items": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "camera_id": e.camera_id,
                "payload": e.payload,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Resumo agregado de analytics",
    tags=["analytics-config"],
)
async def get_analytics_summary(
    claims: CurrentUser,
    db: DbSession,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
) -> AnalyticsSummaryResponse:
    """Contagens agregadas de eventos analytics por câmera e tipo para dashboard."""
    from datetime import timezone, timedelta
    from sqlalchemy import func, select
    from vms.events.models import VmsEventModel

    now = datetime.now(timezone.utc)
    period_start = started_after or (now - timedelta(hours=24))
    period_end = started_before or now

    stmt = (
        select(
            VmsEventModel.camera_id,
            VmsEventModel.event_type,
            func.count().label("cnt"),
        )
        .where(
            VmsEventModel.tenant_id == claims.tenant_id,
            VmsEventModel.event_type.like("analytics.%"),
            VmsEventModel.occurred_at >= period_start,
            VmsEventModel.occurred_at <= period_end,
        )
        .group_by(VmsEventModel.camera_id, VmsEventModel.event_type)
    )

    result = await db.execute(stmt)
    rows = result.all()

    by_type = [
        ROIEventSummary(camera_id=row.camera_id or "", event_type=row.event_type, count=row.cnt)
        for row in rows
    ]
    total = sum(r.count for r in by_type)

    return AnalyticsSummaryResponse(
        period_start=period_start,
        period_end=period_end,
        total_events=total,
        by_type=by_type,
    )


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


@internal_router.post(
    "/internal/analytics/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Ingestão de resultado de analytics — uso interno",
    tags=["internal"],
)
async def ingest_analytics(
    body: AnalyticsIngestRequest,
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> dict:
    """
    Recebe resultado de análise do analytics_service e cria VmsEvent.

    Requer header Authorization: ApiKey <analytics_api_key>.
    """
    settings = get_settings()
    expected = f"ApiKey {settings.analytics_api_key}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Analytics API key inválida ou ausente",
        )

    from vms.events.models import VmsEventModel

    event = VmsEventModel(
        id=str(uuid.uuid4()),
        tenant_id=body.tenant_id,
        event_type=body.event_type,
        payload=body.payload,
        camera_id=body.camera_id,
        occurred_at=datetime.fromisoformat(body.occurred_at),
    )
    db.add(event)
    await db.commit()

    # Publica no event bus para notificações
    try:
        from vms.core.event_bus import publish_event

        await publish_event(
            body.event_type,
            {
                "event_id": event.id,
                "camera_id": body.camera_id,
                "plugin": body.plugin,
                "roi_id": body.roi_id,
                **body.payload,
            },
            tenant_id=body.tenant_id,
        )
    except Exception:
        logger.warning("Falha ao publicar evento analytics no event bus")

    logger.info(
        "Analytics ingest: plugin=%s camera=%s event=%s",
        body.plugin,
        body.camera_id,
        body.event_type,
    )
    return {"status": "created", "event_id": event.id}
