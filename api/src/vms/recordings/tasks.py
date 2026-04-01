"""Tarefas ARQ para processamento de gravações."""
from __future__ import annotations

import logging
import re

import arq
from sqlalchemy.ext.asyncio import AsyncSession

from vms.core.database import get_session_factory
from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
from vms.recordings.service import RecordingService

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")


async def task_index_segment(
    ctx: dict,
    mediamtx_path: str,
    file_path: str,
) -> None:
    """Indexa segmento de gravação no banco e dispara limpeza se necessário."""
    match = _PATH_RE.match(mediamtx_path)
    if not match:
        logger.warning("Path inválido para indexação: %s", mediamtx_path)
        return

    tenant_id = match.group("tenant_id")
    camera_id = match.group("camera_id")

    factory = get_session_factory()
    async with factory() as session:
        try:
            svc = _build_service(session)
            segment = await svc.index_segment(
                tenant_id=tenant_id,
                camera_id=camera_id,
                file_path=file_path,
                mediamtx_path=mediamtx_path,
            )
            await session.commit()
            logger.info("Segmento indexado: %s", file_path)

            # Dispara processamento de analytics pós-gravação
            await _enqueue_analytics(ctx, segment.id, file_path, camera_id, tenant_id)
        except Exception as exc:
            await session.rollback()
            logger.exception("Erro ao indexar segmento: %s", file_path)
            try:
                from vms.core.dlq import record_failure
                await record_failure(
                    ctx["redis"], "task_index_segment", file_path, str(exc),
                )
            except Exception:
                pass
            raise


async def _enqueue_analytics(
    ctx: dict,
    segment_id: str,
    file_path: str,
    camera_id: str,
    tenant_id: str,
) -> None:
    """Enfileira task_analytics_segment no worker do analytics service."""
    try:
        from arq.connections import RedisSettings, create_pool
        from vms.core.config import get_settings

        settings = get_settings()
        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        pool = await create_pool(redis_settings)
        try:
            await pool.enqueue_job(
                "task_analytics_segment",
                segment_id,
                file_path,
                camera_id,
                tenant_id,
            )
        finally:
            await pool.aclose()
        logger.debug("analytics_segment enfileirado para segmento %s", segment_id)
    except Exception:
        logger.exception(
            "Falha ao enfileirar analytics_segment para segmento %s", segment_id
        )


async def task_apply_pending_retention(ctx: dict) -> None:
    """Aplica retention_days_pending para câmeras cujo ciclo atual terminou. Roda diariamente."""
    from datetime import UTC, datetime
    from vms.cameras.models import CameraModel
    from sqlalchemy import select, update as sa_update

    now = datetime.now(UTC)
    factory = get_session_factory()
    async with factory() as session:
        try:
            stmt = select(CameraModel).where(
                CameraModel.retention_days_pending.is_not(None),
                CameraModel.retention_pending_from <= now,
            )
            cameras = (await session.scalars(stmt)).all()

            if cameras:
                ids = [c.id for c in cameras]
                upd = (
                    sa_update(CameraModel)
                    .where(CameraModel.id.in_(ids))
                    .values(
                        retention_days=CameraModel.retention_days_pending,
                        retention_days_pending=None,
                        retention_pending_from=None,
                    )
                )
                await session.execute(upd)
                await session.commit()

            logger.info(
                "Retenção pendente aplicada: %d câmeras atualizadas", len(cameras)
            )
        except Exception:
            await session.rollback()
            logger.exception("Erro ao aplicar retenção pendente")


async def task_cleanup_old_segments(ctx: dict) -> None:
    """Remove segmentos de câmeras com retenção expirada. Roda diariamente."""
    from vms.cameras.models import CameraModel
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        try:
            stmt = select(CameraModel).where(CameraModel.is_active.is_(True))
            cameras = (await session.scalars(stmt)).all()

            svc = _build_service(session)
            total_removed = 0
            for camera in cameras:
                removed = await svc.cleanup_expired_segments(
                    camera.tenant_id, camera.id, camera.retention_days
                )
                total_removed += removed

            await session.commit()
            logger.info("Limpeza concluída: %d segmentos removidos", total_removed)
        except Exception:
            await session.rollback()
            logger.exception("Erro na limpeza de segmentos")


def _build_service(session: AsyncSession) -> RecordingService:
    """Constrói RecordingService com repositórios."""
    return RecordingService(
        RecordingSegmentRepository(session),
        ClipRepository(session),
    )


class WorkerSettings:
    """Configurações do worker ARQ para gravações."""

    functions = [task_index_segment, task_cleanup_old_segments, task_apply_pending_retention]
    redis_settings: arq.connections.RedisSettings | None = None  # definido na inicialização
    cron_jobs = [
        arq.cron(task_cleanup_old_segments, hour=3),       # 3h diariamente
        arq.cron(task_apply_pending_retention, hour=3, minute=15),  # 3h15 diariamente
    ]
