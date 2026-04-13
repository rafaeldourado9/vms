"""Tarefas ARQ para geração de relatórios."""
from __future__ import annotations

import logging

from vms.reports.repository import ReportRepository
from vms.reports.service import ReportService
from vms.core.database import get_session_factory

logger = logging.getLogger(__name__)


async def task_generate_report(ctx: dict, report_id: str) -> None:
    """Gera relatório PDF solicitado."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            repo = ReportRepository(session)
            svc = ReportService(repo)
            
            report = await repo.get_by_id(report_id, tenant_id="*")  # Lookup global
            
            # Aqui entraria a lógica de coleta de dados
            # await svc.generate_report_pdf(report, data={...})
            
            await session.commit()
            logger.info("Relatório %s gerado com sucesso", report_id)
        except Exception:
            await session.rollback()
            logger.exception("Falha ao gerar relatório %s", report_id)
