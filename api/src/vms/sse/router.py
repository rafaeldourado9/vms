"""Rotas SSE — Server-Sent Events via Redis pub/sub."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from vms.core.deps import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/sse",
    summary="Server-Sent Events em tempo real",
    tags=["sse"],
)
async def sse_stream(
    request: Request,
    claims: CurrentUser,
) -> StreamingResponse:
    """
    Stream SSE filtrado por tenant do usuário autenticado.

    Escuta canal Redis `sse:{tenant_id}` e envia eventos ao cliente.
    """
    tenant_id = claims.tenant_id

    async def event_generator():
        """Gera eventos SSE via Redis pub/sub."""
        redis = request.app.state.redis
        channel_name = f"sse:{tenant_id}"

        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
        logger.info("SSE conectado: tenant=%s", tenant_id)

        try:
            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
                else:
                    # Heartbeat para manter conexão viva
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.aclose()
            logger.info("SSE desconectado: tenant=%s", tenant_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def publish_sse_event(
    redis, tenant_id: str, event_type: str, payload: dict
) -> None:
    """Publica evento no canal SSE do tenant via Redis pub/sub."""
    message = json.dumps({"event": event_type, "data": payload})
    await redis.publish(f"sse:{tenant_id}", message)
