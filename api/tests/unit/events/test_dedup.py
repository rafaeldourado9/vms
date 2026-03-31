"""Testes unitários da lógica de deduplicação ALPR via Redis."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from vms.events.domain import AlprDetection
from vms.events.service import EventService


def _make_detection(**overrides) -> AlprDetection:
    """Factory para criar AlprDetection de teste."""
    defaults = {
        "camera_id": "cam-001",
        "tenant_id": "t1",
        "plate": "ABC1D23",
        "confidence": 0.95,
        "manufacturer": "hikvision",
        "timestamp": datetime(2026, 3, 30, 12, 0, 0),
        "raw_payload": {"ANPR": {"licensePlate": "ABC1D23"}},
    }
    defaults.update(overrides)
    return AlprDetection(**defaults)


@pytest.fixture
def event_repo():
    repo = AsyncMock()
    repo.create = AsyncMock(side_effect=lambda e: e)
    return repo


@pytest.fixture
def svc(event_repo):
    return EventService(event_repo)


@pytest.fixture
def redis_mock():
    return AsyncMock()


class TestAlprDedup:
    """Testes da deduplicação ALPR com Redis SET NX EX."""

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_first_event_is_accepted(
        self, mock_settings, mock_pub, svc, event_repo, redis_mock
    ):
        """Primeiro evento para placa+câmera é aceito e persistido."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)  # NX succeeded

        result = await svc.ingest_alpr(_make_detection(), redis_mock)

        assert result is not None
        assert result.plate == "ABC1D23"
        event_repo.create.assert_called_once()
        mock_pub.assert_called_once()

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_duplicate_within_ttl_is_ignored(
        self, mock_settings, mock_pub, svc, event_repo, redis_mock
    ):
        """Segundo evento mesma placa+câmera dentro do TTL é ignorado."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=None)  # NX failed (key exists)

        result = await svc.ingest_alpr(_make_detection(), redis_mock)

        assert result is None
        event_repo.create.assert_not_called()
        mock_pub.assert_not_called()

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_different_plate_is_accepted(
        self, mock_settings, mock_pub, svc, event_repo, redis_mock
    ):
        """Placa diferente na mesma câmera é aceita (chave Redis diferente)."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)

        result = await svc.ingest_alpr(
            _make_detection(plate="XYZ9A00"), redis_mock
        )

        assert result is not None
        assert result.plate == "XYZ9A00"
        event_repo.create.assert_called_once()

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_different_camera_is_accepted(
        self, mock_settings, mock_pub, svc, event_repo, redis_mock
    ):
        """Mesma placa em câmera diferente é aceita (chave Redis diferente)."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)

        result = await svc.ingest_alpr(
            _make_detection(camera_id="cam-002"), redis_mock
        )

        assert result is not None
        event_repo.create.assert_called_once()

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_redis_key_format(
        self, mock_settings, mock_pub, svc, redis_mock
    ):
        """Chave Redis segue padrão alpr:dedup:{camera_id}:{plate}."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)

        await svc.ingest_alpr(_make_detection(), redis_mock)

        redis_mock.set.assert_called_once_with(
            "alpr:dedup:cam-001:ABC1D23", "1", ex=60, nx=True
        )

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_event_type_is_alpr_detected(
        self, mock_settings, mock_pub, svc, redis_mock
    ):
        """Evento criado tem event_type='alpr.detected'."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)

        result = await svc.ingest_alpr(_make_detection(), redis_mock)

        assert result.event_type == "alpr.detected"

    @patch("vms.events.service.publish_event", new_callable=AsyncMock)
    @patch("vms.events.service.get_settings")
    async def test_publish_event_called_with_correct_routing(
        self, mock_settings, mock_pub, svc, redis_mock
    ):
        """Evento publicado no bus com routing key 'alpr.detected'."""
        mock_settings.return_value.alpr_dedup_ttl_seconds = 60
        redis_mock.set = AsyncMock(return_value=True)

        await svc.ingest_alpr(_make_detection(), redis_mock)

        mock_pub.assert_called_once()
        args = mock_pub.call_args
        assert args[0][0] == "alpr.detected"
        assert args[1]["tenant_id"] == "t1"
