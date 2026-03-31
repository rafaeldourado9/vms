"""Testes de integração — CRUD de câmeras via HTTP."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel


@pytest.fixture
async def seeded_data(db_session_factory):
    """Cria tenant + user no banco."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-cam", name="Test", slug="test-cam")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-cam", tenant_id="t-cam", email="admin@test.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        await session.commit()
    token = create_access_token("u-cam", "t-cam", "admin")
    return {"token": token, "tenant_id": "t-cam"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestCamerasCRUD:
    """CRUD de câmeras — /api/v1/cameras."""

    @patch("vms.cameras.service.MediaMTXClient")
    async def test_create_camera(self, mock_mtx_cls, client: AsyncClient, seeded_data, auth_header):
        """POST /cameras cria câmera."""
        mock_mtx = AsyncMock()
        mock_mtx.add_path = AsyncMock(return_value=True)
        mock_mtx_cls.return_value = mock_mtx

        resp = await client.post(
            "/api/v1/cameras",
            json={
                "name": "Entrada Principal",
                "rtsp_url": "rtsp://192.168.1.100:554/stream",
                "manufacturer": "hikvision",
                "location": "Portaria",
            },
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Entrada Principal"
        assert data["tenant_id"] == "t-cam"
        assert data["manufacturer"] == "hikvision"
        assert data["is_active"] is True
        assert data["is_online"] is False

    @patch("vms.cameras.service.MediaMTXClient")
    async def test_list_cameras(self, mock_mtx_cls, client: AsyncClient, seeded_data, auth_header):
        """GET /cameras retorna lista."""
        mock_mtx_cls.return_value = AsyncMock(add_path=AsyncMock(return_value=True))

        # Cria uma câmera primeiro
        await client.post(
            "/api/v1/cameras",
            json={"name": "Cam 1", "rtsp_url": "rtsp://192.168.1.1:554/s"},
            headers=auth_header,
        )
        resp = await client.get("/api/v1/cameras", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    async def test_list_cameras_no_auth(self, client: AsyncClient):
        """GET /cameras sem token retorna 401."""
        resp = await client.get("/api/v1/cameras")
        assert resp.status_code == 401

    @patch("vms.cameras.service.MediaMTXClient")
    async def test_get_camera(self, mock_mtx_cls, client: AsyncClient, seeded_data, auth_header):
        """GET /cameras/{id} retorna câmera."""
        mock_mtx_cls.return_value = AsyncMock(add_path=AsyncMock(return_value=True))

        create_resp = await client.post(
            "/api/v1/cameras",
            json={"name": "Cam X", "rtsp_url": "rtsp://192.168.1.2:554/s"},
            headers=auth_header,
        )
        cam_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/cameras/{cam_id}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json()["id"] == cam_id

    async def test_get_camera_not_found(self, client: AsyncClient, seeded_data, auth_header):
        """GET /cameras/{id} retorna 404 se não existe."""
        resp = await client.get("/api/v1/cameras/nonexistent", headers=auth_header)
        assert resp.status_code == 404
