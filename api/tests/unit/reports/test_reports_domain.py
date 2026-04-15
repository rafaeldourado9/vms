"""Testes unitários do Reports domain — Report, ReportStatus, ReportType."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from vms.reports.domain import (
    Report,
    ReportStatus,
    ReportType,
)
from vms.shared.kernel import ReportId, TenantId


# ─── ReportStatus Enum ──────────────────────────────────────────────────────


class TestReportStatus:
    """Testes do enum ReportStatus."""

    def test_status_values(self):
        """ReportStatus tem valores corretos."""
        assert ReportStatus.PENDING == "pending"
        assert ReportStatus.GENERATING == "generating"
        assert ReportStatus.READY == "ready"
        assert ReportStatus.FAILED == "failed"


# ─── ReportType Enum ────────────────────────────────────────────────────────


class TestReportType:
    """Testes do enum ReportType."""

    def test_type_values(self):
        """ReportType tem valores corretos."""
        assert ReportType.EVENTS_SUMMARY == "events_summary"
        assert ReportType.CAMERAS_STATUS == "cameras_status"
        assert ReportType.RECORDINGS_COVERAGE == "recordings_coverage"
        assert ReportType.AUDIT_TRAIL == "audit_trail"
        assert ReportType.ANALYTICS_EVENTS == "analytics_events"


# ─── Report Entity ───────────────────────────────────────────────────────────


class TestReport:
    """Testes da entidade Report."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    def test_create_with_defaults(self, tenant_id):
        """Report criado com defaults corretos."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
        )
        assert report.report_type == ReportType.EVENTS_SUMMARY
        assert report.status == ReportStatus.PENDING
        assert report.parameters == {}
        assert report.file_path is None
        assert report.sha256_hash is None
        assert report.generated_at is None

    def test_create_with_parameters(self, tenant_id):
        """Report criado com parâmetros."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.AUDIT_TRAIL,
            parameters={
                "from_date": "2026-04-01",
                "to_date": "2026-04-12",
                "actions": ["camera.created", "camera.deleted"],
            },
        )
        assert report.parameters["from_date"] == "2026-04-01"
        assert len(report.parameters["actions"]) == 2

    def test_is_ready_property(self, tenant_id):
        """is_ready retorna True apenas para status READY."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
            status=ReportStatus.READY,
        )
        assert report.is_ready is True

        report.status = ReportStatus.PENDING
        assert report.is_ready is False

        report.status = ReportStatus.GENERATING
        assert report.is_ready is False

    def test_is_failed_property(self, tenant_id):
        """is_failed retorna True apenas para status FAILED."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
            status=ReportStatus.FAILED,
        )
        assert report.is_failed is True

        report.status = ReportStatus.PENDING
        assert report.is_failed is False

    def test_start_generation_from_pending(self, tenant_id):
        """start_generation() funciona a partir de PENDING."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
        )
        assert report.status == ReportStatus.PENDING
        report.start_generation()
        assert report.status == ReportStatus.GENERATING

    def test_start_generation_from_other_status_raises(self, tenant_id):
        """start_generation() lança erro se não estiver em PENDING."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
            status=ReportStatus.READY,
        )
        with pytest.raises(ValueError, match="Não é possível gerar relatório em status 'ready'"):
            report.start_generation()

    def test_mark_ready_from_generating(self, tenant_id):
        """mark_ready() funciona a partir de GENERATING."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
        )
        report.start_generation()
        report.mark_ready(
            file_path="/tmp/reports/report_123.pdf",
            sha256_hash="abc123def456",
        )
        assert report.status == ReportStatus.READY
        assert report.file_path == "/tmp/reports/report_123.pdf"
        assert report.sha256_hash == "abc123def456"
        assert report.generated_at is not None

    def test_mark_ready_from_other_status_raises(self, tenant_id):
        """mark_ready() lança erro se não estiver em GENERATING."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
        )
        with pytest.raises(ValueError, match="Não é possível finalizar relatório em status 'pending'"):
            report.mark_ready(
                file_path="/tmp/reports/report_123.pdf",
                sha256_hash="abc123def456",
            )

    def test_mark_failed(self, tenant_id):
        """mark_failed() muda status para FAILED."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
        )
        report.mark_failed()
        assert report.status == ReportStatus.FAILED

    def test_full_lifecycle(self, tenant_id):
        """Ciclo de vida completo: pending → generating → ready."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.CAMERAS_STATUS,
            parameters={"period": "last_24h"},
        )
        # Inicial: pending
        assert report.status == ReportStatus.PENDING
        assert report.is_ready is False
        assert report.is_failed is False

        # Iniciar geração
        report.start_generation()
        assert report.status == ReportStatus.GENERATING

        # Finalizar
        report.mark_ready(
            file_path="/tmp/reports/cameras_status.pdf",
            sha256_hash="sha256_hash_value",
        )
        assert report.status == ReportStatus.READY
        assert report.is_ready is True
        assert report.file_path == "/tmp/reports/cameras_status.pdf"
        assert report.sha256_hash == "sha256_hash_value"
        assert report.generated_at is not None

    def test_full_lifecycle_failure(self, tenant_id):
        """Ciclo de vida com falha: pending → generating → failed."""
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.ANALYTICS_EVENTS,
        )
        report.start_generation()
        assert report.status == ReportStatus.GENERATING

        report.mark_failed()
        assert report.status == ReportStatus.FAILED
        assert report.is_failed is True
        assert report.file_path is None
        assert report.sha256_hash is None

    def test_created_by_user(self, tenant_id):
        """Report com created_by."""
        user_id = uuid.uuid4()
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.EVENTS_SUMMARY,
            created_by=user_id,
        )
        assert report.created_by == user_id

    def test_scheduled_for(self, tenant_id):
        """Report agendado para futuro."""
        scheduled = datetime(2026, 4, 15, 6, 0, 0)
        report = Report(
            tenant_id=tenant_id,
            report_type=ReportType.AUDIT_TRAIL,
            scheduled_for=scheduled,
        )
        assert report.scheduled_for == scheduled
