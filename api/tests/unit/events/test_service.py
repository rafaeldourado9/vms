"""Testes unitários do EventService (list/get)."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from vms.core.exceptions import NotFoundError
from vms.events.domain import VmsEvent
from vms.events.service import EventService


def _make_event(**overrides) -> VmsEvent:
    defaults = {
        "id": "evt-001",
        "tenant_id": "t1",
        "event_type": "alpr.detected",
        "payload": {"plate": "ABC1D23"},
        "camera_id": "cam-001",
        "plate": "ABC1D23",
        "confidence": 0.95,
        "occurred_at": datetime(2026, 3, 30, 12, 0),
    }
    defaults.update(overrides)
    return VmsEvent(**defaults)


@pytest.fixture
def event_repo():
    return AsyncMock()


@pytest.fixture
def svc(event_repo):
    return EventService(event_repo)


class TestEventServiceList:
    """Testes de listagem de eventos."""

    async def test_list_events_returns_items_and_total(self, svc, event_repo):
        """list_events retorna tupla (items, total)."""
        events = [_make_event(id="e1"), _make_event(id="e2")]
        event_repo.list_by_tenant = AsyncMock(return_value=(events, 2))

        items, total = await svc.list_events("t1")

        assert len(items) == 2
        assert total == 2
        event_repo.list_by_tenant.assert_called_once()

    async def test_list_events_passes_filters(self, svc, event_repo):
        """list_events repassa filtros para o repository."""
        event_repo.list_by_tenant = AsyncMock(return_value=([], 0))

        await svc.list_events(
            "t1", event_type="alpr.detected", plate="ABC", camera_id="c1",
            limit=10, offset=5,
        )

        call_kwargs = event_repo.list_by_tenant.call_args
        assert call_kwargs[1]["event_type"] == "alpr.detected"
        assert call_kwargs[1]["plate"] == "ABC"
        assert call_kwargs[1]["camera_id"] == "c1"
        assert call_kwargs[1]["limit"] == 10
        assert call_kwargs[1]["offset"] == 5


class TestEventServiceGet:
    """Testes de busca de evento por ID."""

    async def test_get_event_found(self, svc, event_repo):
        """Retorna evento quando encontrado."""
        evt = _make_event()
        event_repo.get_by_id = AsyncMock(return_value=evt)

        result = await svc.get_event("evt-001", "t1")

        assert result.id == "evt-001"

    async def test_get_event_not_found_raises(self, svc, event_repo):
        """Lança NotFoundError quando evento não existe."""
        event_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await svc.get_event("nonexistent", "t1")
