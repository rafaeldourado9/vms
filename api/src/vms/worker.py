"""Configuração do worker ARQ."""
from __future__ import annotations

import logging

import arq
from arq.connections import RedisSettings

from vms.core.config import get_settings
from vms.recordings.tasks import task_cleanup_old_segments, task_index_segment
from vms.notifications.tasks import task_dispatch_notification

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Inicializa recursos compartilhados para o worker."""
    import redis.asyncio as aioredis
    from vms.core.database import create_engine, init_db

    settings = get_settings()

    # Banco de dados
    engine = create_engine(settings.database_url)
    init_db(engine)
    ctx["db_engine"] = engine
    logger.info("Worker: banco de dados inicializado")

    # Redis para deduplicação ALPR e cache
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=False)
    ctx["redis"] = redis_client
    logger.info("Worker: Redis conectado")


async def shutdown(ctx: dict) -> None:
    """Fecha recursos do worker."""
    from vms.core.database import close_db

    if "redis" in ctx:
        await ctx["redis"].aclose()

    await close_db()
    logger.info("Worker: recursos encerrados")


class WorkerSettings:
    """Configurações do worker ARQ para tarefas assíncronas."""

    functions = [
        task_index_segment,
        task_cleanup_old_segments,
        task_dispatch_notification,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs = [
        arq.cron(task_cleanup_old_segments, hour=3, minute=0),
    ]
    max_jobs = 50
    job_timeout = 300
