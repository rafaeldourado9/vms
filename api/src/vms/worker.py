"""Configuração dos workers ARQ.

Dois workers:
- WorkerSettings        → fila "arq:high": recordings, notifications, watchdog, cleanup
- LowPriorityWorkerSettings → fila "arq:low": reports PDF (pesados, sem urgência)

Para rodar os dois, adicione no docker-compose:
    worker-high:
        command: python -m arq vms.worker.WorkerSettings
    worker-low:
        command: python -m arq vms.worker.LowPriorityWorkerSettings
"""
from __future__ import annotations

import logging

import arq
from arq.connections import RedisSettings

from vms.infrastructure.config import get_settings
from vms.cameras.tasks import task_camera_watchdog
from vms.recordings.tasks import task_cleanup_old_segments, task_index_segment, task_segment_to_hls
from vms.notifications.tasks import task_dispatch_notification
from vms.reports.tasks import task_auto_monthly_report, task_generate_report

logger = logging.getLogger(__name__)

_ARQ_HIGH = "arq:high"
_ARQ_LOW = "arq:low"


async def startup(ctx: dict) -> None:
    """Inicializa recursos compartilhados para o worker."""
    import httpx
    import redis.asyncio as aioredis
    from vms.infrastructure.database import create_engine, init_db

    settings = get_settings()

    # Banco de dados — pool menor: worker é processo único com tasks async
    engine = create_engine(settings.database_url, for_worker=True)
    init_db(engine)
    ctx["db_engine"] = engine
    logger.info("Worker: banco de dados inicializado")

    # Redis para deduplicação ALPR e cache
    redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=False,
        max_connections=10,
        socket_keepalive=True,
        retry_on_timeout=True,
    )
    ctx["redis"] = redis_client
    logger.info("Worker: Redis conectado")

    # httpx client compartilhado — reutiliza conexões TCP entre jobs (keep-alive)
    # Sem isso cada task_dispatch_notification abre e fecha uma conexão TCP nova.
    ctx["http_client"] = httpx.AsyncClient(
        timeout=10.0,
        limits=httpx.Limits(
            max_connections=50,
            max_keepalive_connections=20,
            keepalive_expiry=30,
        ),
        headers={"User-Agent": "VMS-Webhook/1.0"},
    )
    logger.info("Worker: httpx client inicializado")


async def shutdown(ctx: dict) -> None:
    """Fecha recursos do worker."""
    from vms.infrastructure.database import close_db

    if "http_client" in ctx:
        await ctx["http_client"].aclose()

    if "redis" in ctx:
        await ctx["redis"].aclose()

    await close_db()
    logger.info("Worker: recursos encerrados")


class WorkerSettings:
    """Worker de alta prioridade: recordings, notifications, watchdog.

    Usa a fila padrão do ARQ ("arq:queue") para não exigir _queue_name
    nos enqueue_job existentes.
    """

    functions = [
        task_index_segment,
        task_segment_to_hls,
        task_cleanup_old_segments,
        task_dispatch_notification,
        task_camera_watchdog,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs = [
        arq.cron(task_cleanup_old_segments, hour=3, minute=0),
        arq.cron(task_camera_watchdog, second={0, 30}),
    ]
    max_jobs = 50
    job_timeout = 300


class LowPriorityWorkerSettings:
    """Worker de baixa prioridade: geração de relatórios PDF."""

    queue_name = _ARQ_LOW
    functions = [
        task_generate_report,
        task_auto_monthly_report,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs = [
        # Dia 1 de cada mês às 6h UTC
        arq.cron(task_auto_monthly_report, day=1, hour=6, minute=0),
    ]
    max_jobs = 3        # reports são pesados — limita paralelismo no nível do worker
    job_timeout = 600   # PDF de um mês de dados pode demorar
