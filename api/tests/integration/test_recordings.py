"""Testes de integração — recordings (segmentos e clipes)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from vms.core.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel
from vms.cameras.models import CameraModel


@pytest.fixture
async def seeded_data(db_session_factory):
    """Cria tenant + user + câmera no banco para testes de recordings."""
    async with db_session_factory() as session:
        tenant = TenantModel(id="t-rec", name="Test", slug="test-rec")
        session.add(tenant)
        await session.flush()
        user = UserModel(
            id="u-rec", tenant_id="t-rec", email="admin@rec.com",
            hashed_password=hash_password("senha12345"),
            full_name="Admin", role="admin",
        )
        session.add(user)
        camera = CameraModel(
            id="c-rec", tenant_id="t-rec", name="Cam Rec",
            rtsp_url="rtsp://192.168.1.1:554/s", manufacturer="generic",
        )
        session.add(camera)
        await session.commit()
    token = create_access_token("u-rec", "t-rec", "admin")
    return {"token": token, "tenant_id": "t-rec", "camera_id": "c-rec"}


@pytest.fixture
def auth_header(seeded_data):
    return {"Authorization": f"Bearer {seeded_data['token']}"}


class TestRecordingSegments:
    """GET /api/v1/recordings — listagem de segmentos."""

    async def test_list_segments_empty(
        self, client: AsyncClient, seeded_data, auth_header
    ):
        """Lista vazia quando não há segmentos."""
        resp = await client.get(
            "/api/v1/recordings",
            params={"camera_id": seeded_data["camera_id"]},
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_segments_requires_camera_id(
        self, client: AsyncClient, seeded_data, auth_header
    ):
        """Sem camera_id retorna 422."""
        resp = await client.get(
            "/api/v1/recordings",
            headers=auth_header,
        )
        assert resp.status_code == 422


class TestClips:
    """CRUD de clipes — /api/v1/recordings/clips."""

    async def test_create_clip(
        self, client: AsyncClient, seeded_data, auth_header
    ):
        """POST /recordings/clips cria clipe."""
        now = datetime.now(UTC)
        resp = await client.post(
            "/api/v1/recordings/clips",
            json={
                "camera_id": seeded_data["camera_id"],
                "starts_at": (now - timedelta(minutes=5)).isoformat(),
                "ends_at": now.isoformat(),
            },
            headers=auth_header,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["camera_id"] == seeded_data["camera_id"]
        assert data["status"] == "pending"

    async def test_list_clips_empty(
        self, client: AsyncClient, seeded_data, auth_header
    ):
        """Lista vazia quando não há clipes."""
        resp = await client.get(
            "/api/v1/recordings/clips",
            headers=auth_header,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    async def test_list_clips_no_auth(self, client: AsyncClient):
        """Sem autenticação retorna 401."""
        resp = await client.get("/api/v1/recordings/clips")
        assert resp.status_code == 401
