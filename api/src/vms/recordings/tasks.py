"""Tarefas ARQ para processamento de gravações."""
from __future__ import annotations

import glob as glob_module
import logging
import os
import re
import shutil

import arq
from sqlalchemy.ext.asyncio import AsyncSession

from vms.infrastructure.database import get_session_factory
from vms.recordings.repository import ClipRepository, RecordingSegmentRepository
from vms.recordings.service import RecordingService, build_segment_hls

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
            await svc.index_segment(
                tenant_id=tenant_id,
                camera_id=camera_id,
                file_path=file_path,
                mediamtx_path=mediamtx_path,
            )
            await session.commit()
            logger.info("Segmento indexado: %s", file_path)
        except Exception as exc:
            await session.rollback()
            logger.exception("Erro ao indexar segmento: %s", file_path)
            try:
                from vms.infrastructure.messaging import record_failure
                await record_failure(
                    ctx["redis"], "task_index_segment", file_path, str(exc),
                )
            except Exception:
                pass
            raise


async def task_segment_to_hls(ctx: dict, file_path: str) -> None:
    """Converte segmento fMP4 para chunks TS + playlist HLS.

    Chamado imediatamente após segment_ready para que os chunks estejam
    prontos antes de qualquer requisição de playback.
    """
    m3u8 = await build_segment_hls(file_path)
    if m3u8:
        logger.info("task_segment_to_hls: ok → %s", m3u8)
    else:
        logger.warning("task_segment_to_hls: falhou para %s", file_path)


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


async def task_enforce_disk_quota(ctx: dict) -> None:
    """Remove gravações mais antigas (LRU) se o disco ultrapassar o limite configurado."""
    from sqlalchemy import delete, select

    from vms.infrastructure.config.settings import get_settings
    from vms.recordings.models import RecordingSegmentModel

    settings = get_settings()
    recordings_path = settings.recordings_path
    quota_pct = settings.recordings_disk_quota_pct

    try:
        usage = shutil.disk_usage(recordings_path)
    except FileNotFoundError:
        logger.warning("task_enforce_disk_quota: caminho não encontrado: %s", recordings_path)
        return

    if usage.used / usage.total < quota_pct:
        return

    logger.warning(
        "Disco %.1f%% — acima do limite %.0f%% — LRU eviction iniciada",
        usage.used / usage.total * 100,
        quota_pct * 100,
    )

    factory = get_session_factory()
    removed = 0

    async with factory() as session:
        while True:
            usage = shutil.disk_usage(recordings_path)
            if usage.used / usage.total < quota_pct:
                break

            stmt = (
                select(RecordingSegmentModel)
                .order_by(RecordingSegmentModel.started_at.asc())
                .limit(10)
            )
            segments = (await session.scalars(stmt)).all()
            if not segments:
                logger.error("Sem segmentos para evictar mas disco ainda acima do limite")
                break

            ids = [s.id for s in segments]
            for seg in segments:
                stem = seg.file_path[:-4] if seg.file_path.endswith(".mp4") else seg.file_path
                for path in [seg.file_path, f"{stem}.m3u8", *glob_module.glob(f"{stem}_*.ts")]:
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass
                    except OSError as exc:
                        logger.warning("Não foi possível remover %s: %s", path, exc)

            await session.execute(
                delete(RecordingSegmentModel).where(RecordingSegmentModel.id.in_(ids))
            )
            await session.commit()
            removed += len(ids)

    usage = shutil.disk_usage(recordings_path)
    logger.info(
        "LRU eviction concluída: %d segmentos removidos — disco agora %.1f%%",
        removed,
        usage.used / usage.total * 100,
    )


def _build_service(session: AsyncSession) -> RecordingService:
    """Constrói RecordingService com repositórios."""
    return RecordingService(
        RecordingSegmentRepository(session),
        ClipRepository(session),
    )


class WorkerSettings:
    """Configurações do worker ARQ para gravações."""

    functions = [task_index_segment, task_segment_to_hls, task_cleanup_old_segments, task_enforce_disk_quota]
    redis_settings: arq.connections.RedisSettings | None = None  # definido na inicialização
    cron_jobs = [
        arq.cron(task_cleanup_old_segments, hour=3),       # 3h diariamente
        arq.cron(task_enforce_disk_quota,   minute={0}),   # a cada hora
    ]
