"""Rotas HTTP para relatórios."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from vms.core.deps import CurrentUser, DbSession
from vms.reports.domain import ReportType
from vms.reports.repository import ReportRepository
from vms.reports.schemas import CreateReportRequest, ReportListResponse, ReportResponse
from vms.reports.service import ReportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_svc(db: DbSession) -> ReportService:
    return ReportService(ReportRepository(db))


@router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar relatório",
)
async def request_report(
    body: CreateReportRequest,
    claims: CurrentUser,
    db: DbSession,
) -> ReportResponse:
    """Solicita geração de relatório (processamento assíncrono via ARQ)."""
    svc = _report_svc(db)
    
    # Aqui chamamos direto para simplicidade, em prod idealmente seria via ARQ
    # Para manter a coerência com o plano, vamos criar o registro 'pending'
    report = await svc.create_report(
        tenant_id=claims.tenant_id,
        report_type=body.report_type,
        parameters=body.parameters,
        user_id=claims.user_id,
    )
    
    # Enfileirar task ARQ (simulado aqui com chamada direta)
    # Em produção: await redis.enqueue_job('task_generate_report', report_id=report.id)
    try:
        data = await _collect_data(body.report_type, body.parameters, claims.tenant_id, db)
        await svc.generate_report_pdf(report, data)
    except Exception as exc:
        logger.exception("Falha ao gerar relatório imediatamente: %s", exc)
        
    return ReportResponse.model_validate(report)


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Status do relatório",
)
async def get_report(
    report_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> ReportResponse:
    """Retorna status do relatório."""
    svc = _report_svc(db)
    report = await svc._repo.get_by_id(report_id, claims.tenant_id)
    if not report:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return ReportResponse.model_validate(report)


@router.get(
    "/{report_id}/download",
    summary="Download do relatório",
)
async def download_report(
    report_id: str,
    claims: CurrentUser,
    db: DbSession,
) -> FileResponse:
    """Baixa o PDF do relatório."""
    svc = _report_svc(db)
    report = await svc._repo.get_by_id(report_id, claims.tenant_id)
    if not report or not report.file_path:
        raise HTTPException(status_code=404, detail="Relatório não disponível")
    
    if not report.is_ready:
        raise HTTPException(status_code=400, detail=f"Relatório ainda não está pronto (Status: {report.status})")
        
    return FileResponse(
        path=report.file_path,
        filename=f"relatorio_{report.report_type}_{report.id}.pdf",
        media_type="application/pdf",
    )


@router.get(
    "",
    response_model=ReportListResponse,
    summary="Listar relatórios",
)
async def list_reports(
    claims: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ReportListResponse:
    """Lista relatórios do tenant."""
    svc = _report_svc(db)
    offset = (page - 1) * page_size
    items, total = await svc._repo.list_by_tenant(claims.tenant_id, limit=page_size, offset=offset)
    return ReportListResponse.build(items, total, page, page_size)


async def _collect_data(report_type: ReportType, params: dict, tenant_id: str, db: DbSession) -> dict:
    """Coleta dados do banco para popular o template."""
    # Simulação para demonstração. Em produção, fazer queries reais.
    
    if report_type == ReportType.CAMERAS_STATUS:
        from vms.cameras.models import CameraModel
        from sqlalchemy import select
        stmt = select(CameraModel).where(CameraModel.tenant_id == tenant_id)
        result = await db.execute(stmt)
        cameras = result.scalars().all()
        online = sum(1 for c in cameras if c.is_online)
        return {
            "cameras": cameras,
            "online_count": online,
            "offline_count": len(cameras) - online
        }
        
    # Fallback genérico
    return {"events": [], "summary": {}, "total_events": 0}
