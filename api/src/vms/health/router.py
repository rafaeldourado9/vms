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


@router.get("/metrics", summary="Métricas básicas", tags=["health"])
async def metrics() -> dict:
    """
    Contadores básicos para monitoramento.

    Consulta DB para contagens rápidas. Sem autenticação para scraping.
    """
    try:
        from sqlalchemy import func, select
        from vms.cameras.models import CameraModel
        from vms.events.models import VmsEventModel
        from vms.iam.models import TenantModel, UserModel
        from vms.streaming.models import StreamSessionModel

        factory = get_session_factory()
        async with factory() as session:
            tenants = await session.scalar(select(func.count(TenantModel.id)))
            users = await session.scalar(select(func.count(UserModel.id)))
            cameras = await session.scalar(select(func.count(CameraModel.id)))
            cameras_online = await session.scalar(
                select(func.count(CameraModel.id)).where(CameraModel.is_online.is_(True))
            )
            events_total = await session.scalar(select(func.count(VmsEventModel.id)))
            active_streams = await session.scalar(
                select(func.count(StreamSessionModel.id)).where(
                    StreamSessionModel.ended_at.is_(None)
                )
            )

        return {
            "tenants": tenants or 0,
            "users": users or 0,
            "cameras_total": cameras or 0,
            "cameras_online": cameras_online or 0,
            "events_total": events_total or 0,
            "active_streams": active_streams or 0,
            "version": _VERSION,
        }
    except Exception as exc:
        logger.warning("Metrics falhou: %s", exc)
        return {"error": str(exc), "version": _VERSION}
