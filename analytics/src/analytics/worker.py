"""Worker ARQ do analytics service — processa segmentos pós-gravação."""
from __future__ import annotations

import logging

import arq
from arq.connections import RedisSettings

from analytics.core.config import get_settings
from analytics.core.orchestrator import Orchestrator
from analytics.core.segment_processor import SegmentProcessor
from analytics.core.vms_client import VMSClient

logger = logging.getLogger(__name__)

# Orchestrator singleton compartilhado com o worker
_orchestrator = Orchestrator()
_vms_client = VMSClient()


async def startup(ctx: dict) -> None:
    """Inicializa recursos do worker ARQ."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    await _orchestrator.load_plugins()
    await _vms_client.start()
    ctx["orchestrator"] = _orchestrator
    ctx["vms_client"] = _vms_client
    logger.info(
        "Analytics worker iniciado com %d plugins",
        len(_orchestrator.plugins),
    )


async def shutdown(ctx: dict) -> None:
    """Libera recursos do worker."""
    await _vms_client.close()
    await _orchestrator.stop()
    logger.info("Analytics worker encerrado")


async def task_analytics_segment(
    ctx: dict,
    segment_id: str,
    file_path: str,
    camera_id: str,
    tenant_id: str,
) -> int:
    """
    Processa um segmento .mp4 gravado para analytics pós-gravação.

    Disparada pelo VMS API após indexação do segmento.
    Retorna o número de eventos gerados.
    """
    orchestrator: Orchestrator = ctx["orchestrator"]
    vms_client: VMSClient = ctx["vms_client"]

    processor = SegmentProcessor(
        plugins=orchestrator.plugins,
        vms_client=vms_client,
        fps=get_settings().analytics_fps,
    )
    return await processor.process(
        segment_id=segment_id,
        file_path=file_path,
        camera_id=camera_id,
        tenant_id=tenant_id,
    )


class WorkerSettings:
    """Configurações do worker ARQ de analytics."""

    functions = [task_analytics_segment]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
