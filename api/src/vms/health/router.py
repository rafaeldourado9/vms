"""Endpoint de health check — sem autenticação."""
from __future__ import annotations

import logging

import aio_pika
import redis.asyncio as aioredis
from fastapi import APIRouter
from sqlalchemy import text

from vms.core.config import get_settings
from vms.core.database import get_session_factory

logger = logging.getLogger(__name__)
router = APIRouter()

_VERSION = "1.0.0"


async def _check_db() -> str:
    """Verifica conectividade com o banco de dados."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("Health check DB falhou: %s", exc)
        return f"error: {exc}"


async def _check_redis() -> str:
    """Verifica conectividade com o Redis."""
    try:
        settings = get_settings()
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return "ok"
    except Exception as exc:
        logger.warning("Health check Redis falhou: %s", exc)
        return f"error: {exc}"


async def _check_rabbitmq() -> str:
    """Verifica conectividade com o RabbitMQ."""
    try:
        settings = get_settings()
        connection = await aio_pika.connect(settings.rabbitmq_url, timeout=2)
        await connection.close()
        return "ok"
    except Exception as exc:
        logger.warning("Health check RabbitMQ falhou: %s", exc)
        return f"error: {exc}"


@router.get("/health", summary="Health check", tags=["health"])
async def health_check() -> dict:
    """
    Verifica saúde de todos os serviços dependentes.

    Retorna status agregado sem lançar exceção — degraded se algum serviço falhar.
    Não requer autenticação.
    """
    db_status = await _check_db()
    redis_status = await _check_redis()
    rabbitmq_status = await _check_rabbitmq()

    all_ok = all(
        s == "ok" for s in (db_status, redis_status, rabbitmq_status)
    )

    return {
        "status": "healthy" if all_ok else "degraded",
        "services": {
            "db": db_status,
            "redis": redis_status,
            "rabbitmq": rabbitmq_status,
        },
        "version": _VERSION,
    }
