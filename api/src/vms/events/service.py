"""Casos de uso do bounded context de eventos VMS."""
from __future__ import annotations

import logging
import uuid

from redis.asyncio import Redis

from vms.core.config import get_settings
from vms.core.event_bus import publish_event
from vms.core.exceptions import NotFoundError
from vms.events.domain import AlprDetection, VmsEvent
from vms.events.repository import EventRepositoryPort

logger = logging.getLogger(__name__)

_DEDUP_KEY_PREFIX = "alpr:dedup"


class EventService:
    """Casos de uso de ingestão e consulta de eventos."""

    def __init__(self, event_repo: EventRepositoryPort) -> None:
        self._events = event_repo

    async def ingest_alpr(
        self,
        detection: AlprDetection,
        redis_client: Redis,
    ) -> VmsEvent | None:
        """
        Ingere detecção ALPR com deduplicação Redis.

        Retorna None se a detecção for duplicata dentro do TTL configurado.
        Publica 'alpr.detected' no event bus se aceita.
        """
        dedup_key = f"{_DEDUP_KEY_PREFIX}:{detection.camera_id}:{detection.plate}"
        settings = get_settings()
        ttl = settings.alpr_dedup_ttl_seconds

        is_new = await redis_client.set(dedup_key, "1", ex=ttl, nx=True)
        if not is_new:
            logger.debug(
                "ALPR duplicata ignorada: placa=%s camera=%s",
                detection.plate,
                detection.camera_id,
            )
            return None

        event = VmsEvent(
            id=str(uuid.uuid4()),
            tenant_id=detection.tenant_id,
            event_type="alpr.detected",
            payload={
                "plate": detection.plate,
                "confidence": detection.confidence,
                "manufacturer": detection.manufacturer,
                "image_b64": detection.image_b64,
                "bbox": detection.bbox,
                "raw": detection.raw_payload,
            },
            camera_id=detection.camera_id,
            plate=detection.plate,
            confidence=detection.confidence,
            occurred_at=detection.timestamp,
        )
        saved = await self._events.create(event)

        await publish_event(
            "alpr.detected",
            {
                "event_id": saved.id,
                "camera_id": saved.camera_id,
                "plate": saved.plate,
                "confidence": saved.confidence,
            },
            tenant_id=saved.tenant_id,
        )
        return saved

    async def list_events(
        self,
        tenant_id: str,
        event_type: str | None = None,
        plate: str | None = None,
        camera_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[VmsEvent], int]:
        """Lista eventos com filtros opcionais. Retorna (items, total)."""
        return await self._events.list_by_tenant(
            tenant_id,
            event_type=event_type,
            plate=plate,
            camera_id=camera_id,
            limit=limit,
            offset=offset,
        )

    async def get_event(self, event_id: str, tenant_id: str) -> VmsEvent:
        """Retorna evento por ID. Lança NotFoundError se não encontrado."""
        event = await self._events.get_by_id(event_id, tenant_id)
        if not event:
            raise NotFoundError("Evento", event_id)
        return event
