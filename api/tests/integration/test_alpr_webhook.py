"""Testes de integração — Fluxo A ALPR: webhook → dedup → evento."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel
from vms.cameras.models import CameraModel


@pytest.fixture
async def seeded_data(db_session_factory):
    """Cria tenant + user + câmera para testes ALPR."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-alpr", name="Test", slug="test-alpr")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-alpr", tenant_id="t-alpr", email="admin@alpr.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        camera = CameraModel(
            id="c-alpr", tenant_id="t-alpr", name="Cam ALPR",
            rtsp_url="rtsp://192.168.1.1:554/s", manufacturer="hikvision",
        )
        session.add(camera)
        await session.commit()
    token = create_access_token("u-alpr", "t-alpr", "admin")
    return {"token": token, "tenant_id": "t-alpr", "camera_id": "c-alpr"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestAlprWebhookGeneric:
    """POST /api/v1/webhooks/alpr — webhook ALPR genérico."""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_alpr_creates_event(
        self, mock_pub, client: AsyncClient, app, seeded_data
    ):
        """Webhook ALPR cria evento no banco."""
        # Mock Redis SET NX retorna True (novo)
        app.state.redis.set = AsyncMock(return_value=True)

        resp = await client.post(
            "/api/v1/webhooks/alpr",
            json={
                "camera_id": "c-alpr",
                "plate": "ABC1234",
                "confidence": 0.95,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] is True
        assert data["event_id"] is not None

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_alpr_dedup_ignores_duplicate(
        self, mock_pub, client: AsyncClient, app, seeded_data
    ):
        """Segunda detecção da mesma placa <60s é ignorada."""
        # Mock Redis SET NX retorna None (duplicata)
        app.state.redis.set = AsyncMock(return_value=None)

        resp = await client.post(
            "/api/v1/webhooks/alpr",
            json={
                "camera_id": "c-alpr",
                "plate": "ABC1234",
                "confidence": 0.95,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] is False
        assert data["event_id"] is None
        mock_pub.assert_not_called()


class TestAlprWebhookVendor:
    """POST /api/v1/webhooks/alpr/{manufacturer} — webhook por fabricante."""

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_hikvision_webhook(
        self, mock_pub, client: AsyncClient, app, seeded_data
    ):
        """Webhook Hikvision normaliza payload e cria evento."""
        app.state.redis.set = AsyncMock(return_value=True)

        resp = await client.post(
            "/api/v1/webhooks/alpr/hikvision",
            json={
                "ANPR": {
                    "licensePlate": "XYZ9876",
                    "confidenceLevel": 90,
                    "dateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                },
            },
            params={
                "camera_id": "c-alpr",
                "tenant_id": "t-alpr",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["accepted"] is True

    async def test_unsupported_manufacturer(
        self, client: AsyncClient, seeded_data
    ):
        """Fabricante não suportado retorna 400."""
        resp = await client.post(
            "/api/v1/webhooks/alpr/unknown_brand",
            json={"some": "data"},
            params={
                "camera_id": "c-alpr",
                "tenant_id": "t-alpr",
            },
        )
        assert resp.status_code == 400


class TestEventsAPI:
    """GET /api/v1/events — consulta de eventos."""

    async def test_list_events_empty(
        self, client: AsyncClient, seeded_data, auth_header
    ):
        """Lista vazia quando não há eventos."""
        resp = await client.get(
            "/api/v1/events",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_list_events_after_alpr(
        self, mock_pub, client: AsyncClient, app, seeded_data, auth_header
    ):
        """Após ingestão ALPR via vendor, evento aparece na listagem."""
        app.state.redis.set = AsyncMock(return_value=True)

        # Cria evento via webhook vendor (resolve tenant corretamente)
        await client.post(
            "/api/v1/webhooks/alpr/hikvision",
            json={
                "ANPR": {
                    "licensePlate": "LIST1234",
                    "confidenceLevel": 99,
                    "dateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                },
            },
            params={"camera_id": "c-alpr", "tenant_id": "t-alpr"},
        )

        # Lista eventos
        resp = await client.get(
            "/api/v1/events",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_list_events_no_auth(self, client: AsyncClient):
        """Sem autenticação retorna 401."""
        resp = await client.get("/api/v1/events")
        assert resp.status_code == 401
