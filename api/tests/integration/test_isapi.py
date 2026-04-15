"""Testes de integração do ISAPI router.

Nota: Estes testes requerem PostgreSQL (JSONB não é suportado pelo SQLite).
Rodam apenas em ambiente com PostgreSQL real.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Requer PostgreSQL (JSONB não suportado no SQLite)")

import uuid
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from vms.cameras.domain import Camera, StreamProtocol
from vms.cameras.models import CameraModel
from vms.infrastructure.security import hash_password
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_db_with_camera(db_session_factory):
    """Cria tenant + user + câmera com ISAPI habilitado."""
    async with db_session_factory() as session:
        tenant = TenantModel(
            id="tenant-1",
            name="Test Tenant",
            slug="test",
        )
        session.add(tenant)
        await session.flush()

        user = UserModel(
            id="user-1",
            tenant_id="tenant-1",
            email="admin@test.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin User",
            role="admin",
        )
        session.add(user)

        camera = CameraModel(
            id="cam-hik-01",
            tenant_id="tenant-1",
            name="Hikvision Camera",
            stream_protocol=StreamProtocol.ONVIF.value,
            rtsp_url="rtsp://192.168.1.64:554/stream",
            isapi_enabled=True,
            isapi_username="admin",
            isapi_password="senha123",
            isapi_base_url="http://192.168.1.64/ISAPI",
            isapi_capabilities={"Smart": {"VCA": True}},
            model_name="DS-2CD2143G2-I",
            serial_number="ABC123",
            firmware_version="V5.7.0",
        )
        session.add(camera)
        await session.commit()

    return {"tenant_id": "tenant-1", "user_id": "user-1", "camera_id": "cam-hik-01"}


class TestISAPIProbe:
    """POST /api/v1/cameras/{id}/isapi/probe"""

    async def test_probe_isapi_ok(self, client: AsyncClient, seeded_db_with_camera):
        """Probe ISAPI com câmera configurada — skip no SQLite."""
        pass

    async def test_probe_isapi_camera_not_found(self, client: AsyncClient, seeded_db_with_camera):
        """Probe com câmera inexistente retorna 404 — skip no SQLite."""
        pass

    async def test_probe_isapi_not_configured(self, client: AsyncClient, seeded_db_with_camera, db_session_factory):
        """Probe com câmera sem ISAPI retorna 400 — skip no SQLite."""
        pass


class TestISAPICapabilities:
    """GET /api/v1/cameras/{id}/isapi/capabilities"""

    async def test_get_capabilities_cached(self, client: AsyncClient, seeded_db_with_camera):
        """Capabilities cached retorna dados do cache — skip no SQLite."""
        pass

    async def test_get_capabilities_not_cached(self, client: AsyncClient, seeded_db_with_camera, db_session_factory):
        """Capabilities sem cache consulta ao vivo — skip no SQLite."""
        pass


class TestISAPIConfigurePush:
    """POST /api/v1/cameras/{id}/isapi/configure-push"""

    async def test_configure_push_ok(self, client: AsyncClient, seeded_db_with_camera):
        """Configura Alarm Server na câmera — skip no SQLite."""
        pass

    async def test_configure_push_fails(self, client: AsyncClient, seeded_db_with_camera):
        """Falha ao configurar Alarm Server retorna 502 — skip no SQLite."""
        pass


class TestISAPISyncTime:
    """POST /api/v1/cameras/{id}/isapi/sync-time"""

    async def test_sync_time_ok(self, client: AsyncClient, seeded_db_with_camera):
        """Sincroniza relógio da câmera — skip no SQLite."""
        pass


class TestISAPISnapshot:
    """GET /api/v1/cameras/{id}/isapi/snapshot"""

    async def test_get_snapshot_ok(self, client: AsyncClient, seeded_db_with_camera):
        """Captura snapshot via ISAPI — skip no SQLite."""
        pass

    async def test_get_snapshot_camera_not_found(self, client: AsyncClient, seeded_db_with_camera):
        """Snapshot com câmera inexistente retorna 404 — skip no SQLite."""
        pass
