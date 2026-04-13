"""Tarefas ARQ para geração de relatórios."""
from __future__ import annotations

import logging

from vms.reports.domain import ReportType
from vms.reports.repository import ReportRepository
from vms.reports.service import ReportService
from vms.core.database import get_session_factory

logger = logging.getLogger(__name__)


async def task_generate_report(ctx: dict, report_id: str) -> None:
    """Gera relatório PDF solicitado via ARQ."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            repo = ReportRepository(session)
            svc = ReportService(repo)

            report = await repo.get_by_id(report_id, tenant_id="*")  # Lookup global
            if not report:
                logger.warning("Relatório %s não encontrado para task", report_id)
                return

            # Coletar dados
            data = await _collect_data_for_task(report, session)

            # Gerar PDF
            await svc.generate_report_pdf(report, data)

            await session.commit()
            logger.info("Relatório %s gerado com sucesso", report_id)
        except Exception:
            await session.rollback()
            logger.exception("Falha ao gerar relatório %s", report_id)


async def _collect_data_for_task(report, session) -> dict:
    """Coleta dados para geração assíncrona de relatório."""
    from sqlalchemy import select
    from datetime import datetime, timedelta

    tenant_id = report.tenant_id
    report_type = report.report_type
    params = report.parameters or {}

    if report_type == ReportType.CAMERAS_STATUS:
        from vms.cameras.models import CameraModel
        stmt = select(CameraModel).where(CameraModel.tenant_id == tenant_id)
        result = await session.execute(stmt)
        cameras = result.scalars().all()
        online = sum(1 for c in cameras if c.is_online)
        return {"cameras": cameras, "online_count": online, "offline_count": len(cameras) - online}

    if report_type == ReportType.EVENTS_SUMMARY:
        from vms.events.models import VmsEventModel
        period_days = params.get("period_days", 7)
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = (
            select(VmsEventModel)
            .where(VmsEventModel.tenant_id == tenant_id, VmsEventModel.occurred_at >= cutoff)
            .order_by(VmsEventModel.occurred_at.desc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        events = result.scalars().all()
        type_counts = {}
        for e in events:
            t = e.event_type or "unknown"
            type_counts[t] = type_counts.get(t, 0) + 1
        return {"events": events, "summary": type_counts, "total_events": len(events)}

    if report_type == ReportType.RECORDINGS_COVERAGE:
        from vms.recordings.models import RecordingSegmentModel
        from vms.cameras.models import CameraModel
        period_days = params.get("period_days", 7)
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        cam_stmt = select(CameraModel).where(CameraModel.tenant_id == tenant_id)
        cam_result = await session.execute(cam_stmt)
        cameras = cam_result.scalars().all()
        rec_stmt = select(RecordingSegmentModel).where(
            RecordingSegmentModel.tenant_id == tenant_id,
            RecordingSegmentModel.started_at >= cutoff
        )
        rec_result = await session.execute(rec_stmt)
        recordings = rec_result.scalars().all()
        total_duration = sum(r.duration_seconds or 0 for r in recordings)
        total_size = sum(r.size_bytes or 0 for r in recordings)
        return {
            "cameras": cameras, "recordings": recordings,
            "coverage_stats": {"total_segments": len(recordings), "total_duration_seconds": total_duration},
            "total_duration": total_duration, "total_size": total_size,
        }

    if report_type == ReportType.AUDIT_TRAIL:
        from vms.audit.models import AuditLogModel
        period_days = params.get("period_days", 7)
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.tenant_id == tenant_id, AuditLogModel.occurred_at >= cutoff)
            .order_by(AuditLogModel.occurred_at.desc())
            .limit(500)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()
        action_counts = {}
        for log in logs:
            a = log.action or "unknown"
            action_counts[a] = action_counts.get(a, 0) + 1
        return {"audit_logs": logs, "summary": action_counts, "total_logs": len(logs)}

    if report_type == ReportType.ANALYTICS_EVENTS:
        from vms.analytics.models import AnalyticsEventModel
        period_days = params.get("period_days", 7)
        cutoff = datetime.utcnow() - timedelta(days=period_days)
        stmt = (
            select(AnalyticsEventModel)
            .where(AnalyticsEventModel.tenant_id == tenant_id, AnalyticsEventModel.occurred_at >= cutoff)
            .order_by(AnalyticsEventModel.occurred_at.desc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        events = result.scalars().all()
        plugin_counts = {}
        for e in events:
            p = e.plugin_name or "unknown"
            plugin_counts[p] = plugin_counts.get(p, 0) + 1
        return {"analytics_events": events, "summary": plugin_counts, "total_events": len(events)}

    return {"events": [], "summary": {}, "total_events": 0}
