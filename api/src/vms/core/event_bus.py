"""Publicação de eventos no RabbitMQ via aio-pika (topic exchange)."""

import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import aio_pika
from aio_pika import ExchangeType, Message, connect_robust
from aio_pika.abc import AbstractRobustConnection

from vms.core.config import get_settings

logger = logging.getLogger(__name__)

_EXCHANGE_NAME = "vms_events"

_connection: AbstractRobustConnection | None = None


async def connect_event_bus() -> None:
    """Estabelece conexão robusta com RabbitMQ (reconecta automaticamente)."""
    global _connection
    settings = get_settings()
    _connection = await connect_robust(settings.rabbitmq_url)
    logger.info("Event bus conectado ao RabbitMQ")


async def disconnect_event_bus() -> None:
    """Fecha conexão com RabbitMQ."""
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
        _connection = None


async def publish_event(
    routing_key: str,
    payload: dict,
    *,
    tenant_id: str | None = None,
) -> None:
    """
    Publica evento no exchange topic do RabbitMQ.

    Args:
        routing_key: Chave de roteamento (ex: "alpr.detected", "camera.online")
        payload: Dados do evento (será serializado como JSON)
        tenant_id: ID do tenant (adicionado ao payload automaticamente)

    O exchange é declarado como durable — sobrevive a reinicializações.
    """
    if not _connection or _connection.is_closed:
        logger.warning("Event bus não conectado — evento %s descartado", routing_key)
        return

    try:
        async with _connection.channel() as channel:
            exchange = await channel.declare_exchange(
                _EXCHANGE_NAME,
                ExchangeType.TOPIC,
                durable=True,
            )

            envelope = {
                **payload,
                "event_type": routing_key,
                "published_at": datetime.now(UTC).isoformat(),
            }
            if tenant_id:
                envelope["tenant_id"] = tenant_id

            body = json.dumps(envelope, default=str).encode()
            message = Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )

            await exchange.publish(message, routing_key=routing_key)
            logger.debug("Evento publicado: %s", routing_key)

    except Exception as exc:
        # Publicação falhar não deve derrubar o fluxo principal
        logger.error("Erro ao publicar evento %s: %s", routing_key, exc)
