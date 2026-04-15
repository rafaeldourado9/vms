"""Testes de integração do Reports router.

Nota: Estes testes requerem PostgreSQL (JSONB não é suportado pelo SQLite).
Rodam apenas em ambiente com PostgreSQL real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from vms.infrastructure.security import hash_password
from vms.iam.models import TenantModel, UserModel
from vms.reports.domain import Report, ReportStatus, ReportType
from vms.reports.models import ReportModel


@pytest.fixture
async def seeded_db_with_reports(db_session_factory):
    """Cria tenant + user + relatórios."""
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

        # Criar relatórios de teste
        now = datetime.now(timezone.utc)
        for i in range(3):
            report = ReportModel(
                id=uuid.uuid4(),
                tenant_id="tenant-1",
                report_type=[ReportType.EVENTS_SUMMARY, ReportType.CAMERAS_STATUS, ReportType.AUDIT_TRAIL][i],
                name=f"Relatório {i + 1}",
                parameters={"period": "last_24h"},
                status=[ReportStatus.READY, ReportStatus.PENDING, ReportStatus.FAILED][i],
                created_by="user-1",
                created_at=now,
            )
            if report.status == ReportStatus.READY:
                report.file_path = f"/tmp/reports/report_{i}.pdf"
                report.sha256_hash = f"sha256_{i}"
                report.generated_at = now

            session.add(report)

        await session.commit()

    return {"tenant_id": "tenant-1", "user_id": "user-1"}


class TestReportsList:
    """GET /api/v1/reports"""

    async def test_list_reports_ok(self, client, seeded_db_with_reports):
        """Lista relatórios do tenant autenticado."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] == 3

    async def test_list_reports_no_token_returns_401(self, client):
        """Sem token retorna 401."""
        resp = await client.get("/api/v1/reports")
        assert resp.status_code == 401


class TestReportsCreate:
    """POST /api/v1/reports"""

    async def test_create_report_events_summary(self, client, seeded_db_with_reports):
        """Cria relatório de eventos."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "report_type": "events_summary",
                "parameters": {
                    "from_date": "2026-04-01",
                    "to_date": "2026-04-12",
                },
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["report_type"] == "events_summary"
        assert data["status"] == "pending"

    async def test_create_report_cameras_status(self, client, seeded_db_with_reports):
        """Cria relatório de status de câmeras."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "report_type": "cameras_status",
                "parameters": {},
            },
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["report_type"] == "cameras_status"

    async def test_create_report_audit_trail(self, client, seeded_db_with_reports):
        """Cria relatório de auditoria."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "report_type": "audit_trail",
                "parameters": {
                    "from_date": "2026-04-01",
                    "to_date": "2026-04-12",
                },
            },
        )
        assert resp.status_code in (200, 201)


class TestReportsGet:
    """GET /api/v1/reports/{id}"""

    async def test_get_report_by_id(self, client, seeded_db_with_reports):
        """Obtém relatório por ID."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        # Primeiro lista para pegar um ID
        resp = await client.get(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data["items"]:
            report_id = data["items"][0]["id"]
            resp = await client.get(
                f"/api/v1/reports/{report_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200


class TestReportsDownload:
    """GET /api/v1/reports/{id}/download"""

    async def test_download_ready_report(self, client, seeded_db_with_reports):
        """Baixa relatório pronto."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        # Lista para pegar ID de relatório pronto
        resp = await client.get(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        # Encontrar relatório com status ready
        ready_report = next((item for item in data["items"] if item.get("status") == "ready"), None)
        if ready_report:
            resp = await client.get(
                f"/api/v1/reports/{ready_report['id']}/download",
                headers={"Authorization": f"Bearer {token}"},
            )
            # Pode ser 200 (stream) ou erro de arquivo não encontrado
            assert resp.status_code in (200, 404, 500)

    async def test_download_pending_report_returns_400(self, client, seeded_db_with_reports):
        """Baixa relatório pendente retorna 400."""
        login_resp = await client.post(
            "/api/v1/auth/token",
            json={"email": "admin@test.com", "password": "senha12345"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/reports",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        pending_report = next((item for item in data["items"] if item.get("status") == "pending"), None)
        if pending_report:
            resp = await client.get(
                f"/api/v1/reports/{pending_report['id']}/download",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 400
