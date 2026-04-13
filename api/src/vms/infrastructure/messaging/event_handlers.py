"""
Exemplo de registro de Domain Events e handlers.

Este arquivo demonstra como:
1. Registrar Domain Events no EventRegistry
2. Subscrever handlers para tipos de eventos
3. Publicar eventos após commit

DEVE ser chamado no lifespan da aplicação (main.py).
"""
from __future__ import annotations

import logging

from vms.cameras.domain import (
    CameraActivated,
    CameraAnalyticsDisabled,
    CameraAnalyticsEnableded,
    CameraCreated,
    CameraDeactivated,
)
from vms.infrastructure.messaging.event_bus import DomainEventBus, EventRegistry
from vms.recordings.domain import ClipFailed, ClipReady, ClipRequested, SegmentIndexed
from vms.shared.events import DomainEvent
from vms.vod.domain import (
    VODStreamCreated,
    VODStreamFailed,
    VODStreamGenerationStarted,
    VODStreamReady,
)

logger = logging.getLogger(__name__)


def register_all_events(registry: EventRegistry) -> None:
    """
    Registra todos os Domain Events no registry.

    Deve ser chamado uma vez no startup da aplicação.
    """
    # Camera events
    registry.register("CameraCreated", CameraCreated)
    registry.register("CameraActivated", CameraActivated)
    registry.register("CameraDeactivated", CameraDeactivated)
    registry.register("CameraAnalyticsEnableded", CameraAnalyticsEnableded)
    registry.register("CameraAnalyticsDisabled", CameraAnalyticsDisabled)

    # Recording events
    registry.register("SegmentIndexed", SegmentIndexed)
    registry.register("ClipRequested", ClipRequested)
    registry.register("ClipReady", ClipReady)
    registry.register("ClipFailed", ClipFailed)

    # VOD events
    registry.register("VODStreamCreated", VODStreamCreated)
    registry.register("VODStreamGenerationStarted", VODStreamGenerationStarted)
    registry.register("VODStreamReady", VODStreamReady)
    registry.register("VODStreamFailed", VODStreamFailed)

    logger.info("✅ %d Domain Events registrados", len(registry._event_types))


async def subscribe_all_handlers(bus: DomainEventBus | None) -> None:
    """
    Subscreve todos os handlers de eventos.

    Deve ser chamado uma vez no startup da aplicação.
    Se bus for None, usa o event_bus global.
    """
    from vms.infrastructure.messaging.event_bus import event_bus as global_bus

    target_bus = bus or global_bus
    if target_bus is None:
        logger.warning("Event bus não disponível para subscrever handlers")
        return

    # Exemplo: handler para CameraActivated
    async def on_camera_activated(event: CameraActivated) -> None:
        logger.info(
            "Câmera ativou: camera_id=%s tenant_id=%s",
            event.camera_id,
            event.tenant_id,
        )
        # Aqui poderia:
        # - Publicar notificação SSE
        # - Atualizar cache
        # - Disparar webhook

    # Exemplo: handler para ClipReady
    async def on_clip_ready(event: ClipReady) -> None:
        logger.info(
            "Clipe pronto: clip_id=%s file_path=%s",
            event.clip_id,
            event.file_path,
        )
        # Aqui poderia:
        # - Enviar notificação por email
        # - Atualizar status no banco
        # - Disparar webhook para cliente

    # Exemplo: handler para VODStreamReady
    async def on_vod_stream_ready(event: VODStreamReady) -> None:
        logger.info(
            "VOD Stream pronto: stream_id=%s playlist=%s",
            event.stream_id,
            event.playlist_path,
        )
        # Aqui poderia:
        # - Invalidar cache de URLs
        # - Notificar frontend via SSE

    # Subscrever handlers
    target_bus.subscribe("CameraActivated", on_camera_activated)
    target_bus.subscribe("ClipReady", on_clip_ready)
    target_bus.subscribe("VODStreamReady", on_vod_stream_ready)

    logger.info("✅ %d handlers de eventos subscritos", target_bus.handler_count)
