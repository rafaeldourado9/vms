"""
Testes unitários do Event Bus (Redis pub/sub).

Cobre:
- EventRegistry: register e reconstruct
- DomainEventBus: subscribe, publish, publish_many
- Handlers locais são executados
- Falhas em handlers são logadas mas não propagam
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from vms.cameras.domain import CameraActivated
from vms.infrastructure.messaging.event_bus import DomainEventBus, EventRegistry
from vms.shared.events import DomainEvent
from vms.shared.kernel import CameraId, TenantId


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock de Redis async."""
    redis = AsyncMock()
    redis.publish = AsyncMock()
    redis.pubsub.return_value = AsyncMock()
    return redis


@pytest.fixture
def registry() -> EventRegistry:
    """Registry com CameraActivated registrado."""
    reg = EventRegistry()
    reg.register("CameraActivated", CameraActivated)
    return reg


@pytest.fixture
def event() -> CameraActivated:
    """Evento de exemplo."""
    return CameraActivated(
        camera_id=CameraId.new(),
        tenant_id=TenantId.new(),
    )


# ─── Testes: EventRegistry ───────────────────────────────────────────────────

class TestEventRegistry:
    """Testes de EventRegistry."""

    def test_register_and_reconstruct(self):
        # Given
        registry = EventRegistry()
        registry.register("CameraActivated", CameraActivated)
        camera_id = CameraId.new()
        tenant_id = TenantId.new()
        data = {
            "event_type": "CameraActivated",
            "camera_id": str(camera_id),
            "tenant_id": str(tenant_id),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }

        # When
        event = registry.reconstruct(data)

        # Then
        assert event is not None
        assert isinstance(event, CameraActivated)
        assert event.event_type == "CameraActivated"

    def test_reconstruct_unregistered_type(self):
        # Given
        registry = EventRegistry()
        data = {"event_type": "UnknownEvent"}

        # When
        event = registry.reconstruct(data)

        # Then
        assert event is None

    def test_reconstruct_missing_event_type(self):
        # Given
        registry = EventRegistry()
        data = {"foo": "bar"}

        # When
        event = registry.reconstruct(data)

        # Then
        assert event is None


# ─── Testes: DomainEventBus ──────────────────────────────────────────────────

class TestDomainEventBus:
    """Testes de DomainEventBus."""

    @pytest.mark.asyncio
    async def test_publish_calls_redis(self, mock_redis: AsyncMock, registry: EventRegistry, event: CameraActivated):
        # Given
        bus = DomainEventBus(redis=mock_redis, registry=registry)

        # When
        await bus.publish(event)

        # Then
        mock_redis.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handler_is_executed(self, mock_redis: AsyncMock, registry: EventRegistry, event: CameraActivated):
        # Given
        bus = DomainEventBus(redis=mock_redis, registry=registry)
        handler_called = False

        async def handler(evt: CameraActivated) -> None:
            nonlocal handler_called
            handler_called = True

        bus.subscribe("CameraActivated", handler)

        # When
        await bus.publish(event)

        # Then
        assert handler_called is True

    @pytest.mark.asyncio
    async def test_handler_failure_does_not_propagate(self, mock_redis: AsyncMock, registry: EventRegistry, event: CameraActivated):
        # Given
        bus = DomainEventBus(redis=mock_redis, registry=registry)

        async def failing_handler(evt: CameraActivated) -> None:
            raise RuntimeError("Handler failed")

        bus.subscribe("CameraActivated", failing_handler)

        # When/Then — não deve propagar exceção
        await bus.publish(event)

    @pytest.mark.asyncio
    async def test_publish_many(self, mock_redis: AsyncMock, registry: EventRegistry):
        # Given
        bus = DomainEventBus(redis=mock_redis, registry=registry)
        events = [
            CameraActivated(camera_id=CameraId.new(), tenant_id=TenantId.new()),
            CameraActivated(camera_id=CameraId.new(), tenant_id=TenantId.new()),
        ]

        # When
        await bus.publish_many(events)

        # Then
        assert mock_redis.publish.await_count == 2

    def test_handler_count(self, mock_redis: AsyncMock, registry: EventRegistry):
        # Given
        bus = DomainEventBus(redis=mock_redis, registry=registry)

        async def handler1(evt: CameraActivated) -> None: pass
        async def handler2(evt: CameraActivated) -> None: pass

        bus.subscribe("CameraActivated", handler1)
        bus.subscribe("CameraActivated", handler2)

        # Then
        assert bus.handler_count == 2
