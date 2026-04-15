"""Testes unitários do ReportService."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vms.reports.domain import Report, ReportStatus, ReportType
from vms.reports.repository import ReportRepositoryPort
from vms.reports.service import ReportService
from vms.shared.kernel import ReportId, TenantId


class TestReportService:
    """Testes do ReportService."""

    @pytest.fixture
    def repo(self):
        """Repository mockado."""
        repo = AsyncMock(spec=ReportRepositoryPort)

        async def fake_create(report: Report) -> Report:
            return report

        async def fake_update(report: Report) -> Report:
            return report

        async def fake_get_by_id(report_id: str, tenant_id: str) -> Report | None:
            return None

        repo.create = AsyncMock(side_effect=fake_create)
        repo.update = AsyncMock(side_effect=fake_update)
        repo.get_by_id = AsyncMock(side_effect=fake_get_by_id)
        repo.list_by_tenant = AsyncMock(return_value=([], 0))
        return repo

    @pytest.fixture
    def svc(self, repo):
        return ReportService(repo)

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    async def test_create_report(self, svc, repo, tenant_id):
        """create_report cria relatório com status pending."""
        result = await svc.create_report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
            parameters={"period": "last_24h"},
        )
        assert result.report_type == ReportType.EVENTS_SUMMARY
        assert result.status == ReportStatus.PENDING
        assert result.parameters == {"period": "last_24h"}
        repo.create.assert_called_once()

    async def test_create_report_with_user(self, svc, repo, tenant_id):
        """create_report registra created_by."""
        user_id = uuid.uuid4()
        result = await svc.create_report(
            tenant_id=tenant_id,
            report_type=ReportType.AUDIT_TRAIL,
            parameters={},
            user_id=user_id,
        )
        assert result.created_by == user_id

    async def test_get_report(self, svc, repo):
        """get_report delega para repositório."""
        await svc.get_report("report-123", "tenant-1")
        repo.get_by_id.assert_called_once_with("report-123", "tenant-1")

    async def test_list_reports(self, svc, repo, tenant_id):
        """list_reports com paginação."""
        await svc.list_reports(tenant_id, page=2, page_size=10)
        repo.list_by_tenant.assert_called_once()
        call_kwargs = repo.list_by_tenant.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 10  # (page-1) * page_size

    async def test_get_report_title(self, svc):
        """_get_report_title retorna títulos corretos."""
        assert svc._get_report_title(ReportType.EVENTS_SUMMARY) == "Relatório de Eventos"
        assert svc._get_report_title(ReportType.CAMERAS_STATUS) == "Status de Câmeras"
        assert svc._get_report_title(ReportType.RECORDINGS_COVERAGE) == "Cobertura de Gravações"
        assert svc._get_report_title(ReportType.AUDIT_TRAIL) == "Trilha de Auditoria"
        assert svc._get_report_title(ReportType.ANALYTICS_EVENTS) == "Eventos de Analytics"

    async def test_get_report_title_unknown(self, svc):
        """_get_report_title retorna default para tipo desconhecido."""
        assert svc._get_report_title("unknown_type") == "Relatório VMS"


class TestReportServiceGeneratePdf:
    """Testes da geração de PDF."""

    @pytest.fixture
    def repo(self):
        repo = AsyncMock(spec=ReportRepositoryPort)
        async def fake_update(report: Report) -> Report:
            return report
        repo.update = AsyncMock(side_effect=fake_update)
        return repo

    @pytest.fixture
    def svc(self, repo):
        return ReportService(repo)

    async def test_generate_report_pdf_success(self, svc, repo):
        """generate_report_pdf gera PDF com sucesso."""
        report = Report(
            report_type=ReportType.EVENTS_SUMMARY,
            parameters={"period": "last_24h"},
        )
        data = {"total_events": 150, "events": []}

        # Mock das funções de PDF
        with patch("vms.reports.service.render_template") as mock_render:
            with patch("vms.reports.service.generate_pdf") as mock_pdf:
                with patch("vms.reports.service.Sha256Hash") as mock_hash:
                    mock_render.return_value = "<html>...</html>"
                    mock_pdf.return_value = b"pdf_bytes"
                    mock_hash.from_file.return_value.value = "sha256_hash_value"

                    result = await svc.generate_report_pdf(report, data)

                    assert result.status == ReportStatus.READY
                    assert result.sha256_hash == "sha256_hash_value"
                    assert result.generated_at is not None
                    mock_render.assert_called_once()
                    mock_pdf.assert_called_once()

    async def test_generate_report_pdf_failure(self, svc, repo):
        """generate_report_pdf marca como failed em caso de erro."""
        report = Report(
            report_type=ReportType.EVENTS_SUMMARY,
            parameters={},
        )
        data = {}

        with patch("vms.reports.service.render_template", side_effect=Exception("Template not found")):
            with pytest.raises(Exception, match="Template not found"):
                await svc.generate_report_pdf(report, data)

            assert report.status == ReportStatus.FAILED
