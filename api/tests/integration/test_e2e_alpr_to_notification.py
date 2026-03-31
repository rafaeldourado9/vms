"""E2E: ALPR → Evento → Avaliação de regra → NotificationLog.

Simula o fluxo completo sem serviços externos (Redis mockado, event bus mockado).
"""
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
    """Cria tenant + user + câmera para E2E."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-e2e", name="Test", slug="test-e2e")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-e2e", tenant_id="t-e2e", email="admin@e2e.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        camera = CameraModel(
            id="c-e2e", tenant_id="t-e2e", name="Cam E2E",
            rtsp_url="rtsp://192.168.1.1:554/s", manufacturer="hikvision",
        )
        session.add(camera)
        await session.commit()
    token = create_access_token("u-e2e", "t-e2e", "admin")
    return {"token": token, "tenant_id": "t-e2e", "camera_id": "c-e2e"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestE2EAlprToNotification:
    """Fluxo completo: ALPR → Evento → Regra match → Dispatch."""

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    @patch("vms.core.event_bus.publish_event", new_callable=AsyncMock)
    async def test_full_flow(
        self,
        mock_pub,
        mock_httpx_cls,
        client: AsyncClient,
        app,
        seeded_data,
        auth_header,
    ):
        """
        1. Cria regra de notificação para alpr.*
        2. Envia webhook ALPR
        3. Avalia regras manualmente (simula consumer)
        4. Verifica que NotificationLog foi criado
        """
        # Mock Redis dedup
        app.state.redis.set = AsyncMock(return_value=True)

        # Mock httpx para dispatch do webhook
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.text = "ok"
        mock_httpx_instance = AsyncMock()
        mock_httpx_instance.__aenter__ = AsyncMock(return_value=mock_httpx_instance)
        mock_httpx_instance.__aexit__ = AsyncMock(return_value=None)
        mock_httpx_instance.post = AsyncMock(return_value=mock_response)
        mock_httpx_cls.return_value = mock_httpx_instance

        # 1. Criar regra de notificação
        rule_resp = await client.post(
            "/api/v1/notifications/rules",
            json={
                "name": "Alerta ALPR E2E",
                "event_type_pattern": "alpr.*",
                "destination_url": "https://hooks.example.com/e2e",
                "webhook_secret": "e2e-secret-key-1234",
            },
            headers=auth_header,
        )
        assert rule_resp.status_code == 201

        # 2. Enviar webhook ALPR via vendor endpoint
        alpr_resp = await client.post(
            "/api/v1/webhooks/alpr/hikvision",
            json={
                "ANPR": {
                    "licensePlate": "E2E1234",
                    "confidenceLevel": 98,
                    "dateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                },
            },
            params={"camera_id": "c-e2e", "tenant_id": "t-e2e"},
        )
        assert alpr_resp.status_code == 202
        event_id = alpr_resp.json()["event_id"]
        assert event_id is not None

        # 3. Simular evaluate_and_dispatch (normalmente feito pelo consumer)
        from vms.notifications.service import build_notification_service
        from vms.core.deps import get_db

        async for db in app.dependency_overrides[get_db]():
            svc = build_notification_service(db)
            logs = await svc.evaluate_and_dispatch(
                tenant_id="t-e2e",
                event_type="alpr.detected",
                event_id=event_id,
                payload={"plate": "E2E1234", "confidence": 0.98},
            )
            assert len(logs) == 1
            assert logs[0].status.value == "success"
            break

        # 4. Verificar log na API
        logs_resp = await client.get(
            "/api/v1/notifications/logs",
            headers=auth_header,
        )
        assert logs_resp.status_code == 200
        assert len(logs_resp.json()) >= 1
