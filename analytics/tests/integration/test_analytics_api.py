"""Testes de integração da API do analytics_service."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from analytics.core.config import Settings, get_settings
from analytics.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Settings para testes."""
    return Settings(
        vms_api_url="http://localhost:8000",
        vms_analytics_api_key="test-analytics-key",
        redis_url="redis://localhost:6379/15",
        yolo_model_path="yolov8n.pt",
    )


@pytest.fixture
def app(test_settings: Settings):
    """App FastAPI para testes."""
    from analytics.core.config import get_settings as _gs
    from analytics.core import config as config_mod

    original = config_mod.get_settings

    @__import__("functools").lru_cache
    def _override() -> Settings:
        return test_settings

    config_mod.get_settings = _override
    application = create_app()
    yield application
    config_mod.get_settings = original


@pytest.fixture
async def client(app) -> AsyncClient:
    """HTTP client para testes."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


# ── Testes ────────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Testes do health check do analytics_service."""

    @pytest.mark.asyncio
    async def test_health_retorna_200(self, client: AsyncClient):
        """GET /health deve retornar status healthy."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "plugins_loaded" in data
        assert "plugin_names" in data

    @pytest.mark.asyncio
    async def test_health_mostra_plugins(self, client: AsyncClient):
        """Health deve listar plugins carregados (pode ser 0 em teste sem modelo)."""
        resp = await client.get("/health")
        data = resp.json()
        assert isinstance(data["plugin_names"], list)


class TestIngestEndpoint:
    """Testes do endpoint de ingestão de analytics."""

    @pytest.mark.asyncio
    async def test_ingest_sem_auth_retorna_401(self, client: AsyncClient):
        """POST /internal/analytics/ingest sem API key deve retornar 401."""
        resp = await client.post(
            "/internal/analytics/ingest",
            json={
                "plugin": "intrusion_detection",
                "camera_id": "cam-001",
                "tenant_id": "tenant-001",
                "roi_id": "roi-001",
                "event_type": "analytics.intrusion.detected",
                "payload": {},
                "occurred_at": "2026-03-30T12:00:00",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ingest_com_auth_retorna_201(self, client: AsyncClient):
        """POST /internal/analytics/ingest com API key válida deve retornar 201."""
        resp = await client.post(
            "/internal/analytics/ingest",
            json={
                "plugin": "intrusion_detection",
                "camera_id": "cam-001",
                "tenant_id": "tenant-001",
                "roi_id": "roi-001",
                "event_type": "analytics.intrusion.detected",
                "payload": {"detection_count": 1},
                "occurred_at": "2026-03-30T12:00:00",
            },
            headers={"Authorization": "ApiKey test-analytics-key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_ingest_com_auth_errada_retorna_401(self, client: AsyncClient):
        """POST /internal/analytics/ingest com key errada deve retornar 401."""
        resp = await client.post(
            "/internal/analytics/ingest",
            json={
                "plugin": "people_count",
                "camera_id": "cam-001",
                "tenant_id": "tenant-001",
                "roi_id": "roi-001",
                "event_type": "analytics.people.count",
                "payload": {},
                "occurred_at": "2026-03-30T12:00:00",
            },
            headers={"Authorization": "ApiKey wrong-key"},
        )
        assert resp.status_code == 401
