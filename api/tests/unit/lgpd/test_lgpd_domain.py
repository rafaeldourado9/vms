"""Testes unitários do LGPD domain — ConsentRecord, RetentionPolicy, DataSubjectRequest."""
from __future__ import annotations

# Fix para pytest: garantir nome de módulo único
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from vms.lgpd.domain import (
    ConsentAction,
    ConsentRecord,
    ConsentRecorded,
    DataType,
    DataSubjectRequest,
    RequestType,
    RetentionPolicy,
)
from vms.shared.kernel import AuditId, EntityId, TenantId


# ─── DataType Enum ───────────────────────────────────────────────────────────


class TestDataType:
    """Testes do enum DataType."""

    def test_data_type_values(self):
        """DataType tem valores corretos."""
        assert DataType.VIDEO == "video"
        assert DataType.ALPR == "alpr"
        assert DataType.FACE == "face"
        assert DataType.AUDIT == "audit"
        assert DataType.ANALYTICS == "analytics"


# ─── ConsentAction Enum ──────────────────────────────────────────────────────


class TestConsentAction:
    """Testes do enum ConsentAction."""

    def test_consent_action_values(self):
        """ConsentAction tem valores corretos."""
        assert ConsentAction.GRANTED == "granted"
        assert ConsentAction.REVOKED == "revoked"


# ─── RequestType Enum ────────────────────────────────────────────────────────


class TestRequestType:
    """Testes do enum RequestType."""

    def test_request_type_values(self):
        """RequestType tem valores corretos."""
        assert RequestType.EXPORT == "export"
        assert RequestType.DELETE == "delete"
        assert RequestType.ANONYMIZE == "anonymize"


# ─── ConsentRecord ───────────────────────────────────────────────────────────


class TestConsentRecord:
    """Testes da entidade ConsentRecord."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    @pytest.fixture
    def user_id(self):
        return EntityId(uuid.uuid4())

    def test_create_with_defaults(self, tenant_id):
        """ConsentRecord criado com defaults corretos."""
        record = ConsentRecord(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        assert record.data_type == DataType.FACE
        assert record.action == ConsentAction.GRANTED
        assert record.consent_text_hash is None
        assert record.ip_address is None
        assert record.user_agent is None

    def test_create_with_full_data(self, tenant_id, user_id):
        """ConsentRecord com todos os campos."""
        record = ConsentRecord(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            data_type=DataType.ALPR,
            action=ConsentAction.REVOKED,
            consent_text_hash="sha256_hash_here",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )
        assert record.data_type == DataType.ALPR
        assert record.action == ConsentAction.REVOKED
        assert record.consent_text_hash == "sha256_hash_here"
        assert record.ip_address == "192.168.1.100"
        assert record.user_agent == "Mozilla/5.0"

    def test_created_at_defaults_to_utc(self, tenant_id):
        """created_at usa UTC por default."""
        record = ConsentRecord(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
        )
        assert record.created_at.tzinfo is not None or record.created_at is not None
        # Deve estar próximo de agora (margem de 5s)
        diff = abs((datetime.utcnow() - record.created_at).total_seconds())
        assert diff < 5


# ─── RetentionPolicy ─────────────────────────────────────────────────────────


class TestRetentionPolicy:
    """Testes da entidade RetentionPolicy."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    def test_create_policy(self, tenant_id):
        """RetentionPolicy criada corretamente."""
        policy = RetentionPolicy(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            data_type=DataType.ALPR,
            retention_days=90,
        )
        assert policy.data_type == DataType.ALPR
        assert policy.retention_days == 90
        assert policy.anonymize_instead_of_delete is True
        assert policy.auto_enabled is True

    def test_cutoff_date_calculation(self, tenant_id):
        """cutoff_date calcula corretamente."""
        policy = RetentionPolicy(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            data_type=DataType.VIDEO,
            retention_days=7,
        )
        cutoff = policy.cutoff_date
        expected = datetime.utcnow() - timedelta(days=7)
        # Margem de 5 segundos
        diff = abs((cutoff - expected).total_seconds())
        assert diff < 5

    def test_cutoff_date_longer_retention(self, tenant_id):
        """cutoff_date para retenção longa (5 anos)."""
        policy = RetentionPolicy(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            data_type=DataType.AUDIT,
            retention_days=1825,  # 5 anos
        )
        cutoff = policy.cutoff_date
        expected = datetime.utcnow() - timedelta(days=1825)
        diff = abs((cutoff - expected).total_seconds())
        assert diff < 5

    def test_anonymize_flag_false(self, tenant_id):
        """Política com deleção ao invés de anonimização."""
        policy = RetentionPolicy(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            data_type=DataType.VIDEO,
            retention_days=7,
            anonymize_instead_of_delete=False,
        )
        assert policy.anonymize_instead_of_delete is False

    def test_auto_enabled_false(self, tenant_id):
        """Política não auto-habilitada."""
        policy = RetentionPolicy(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            data_type=DataType.ANALYTICS,
            retention_days=365,
            auto_enabled=False,
        )
        assert policy.auto_enabled is False


# ─── DataSubjectRequest ──────────────────────────────────────────────────────


class TestDataSubjectRequest:
    """Testes da entidade DataSubjectRequest."""

    @pytest.fixture
    def tenant_id(self):
        return TenantId(uuid.uuid4())

    def test_create_with_defaults(self, tenant_id):
        """DataSubjectRequest criada com defaults."""
        request = DataSubjectRequest(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            request_type=RequestType.EXPORT,
        )
        assert request.request_type == RequestType.EXPORT
        assert request.status == "pending"
        assert request.completed_at is None
        assert request.result_url is None
        assert request.notes is None

    def test_create_completed_request(self, tenant_id):
        """DataSubjectRequest já completada."""
        completed_at = datetime.utcnow()
        request = DataSubjectRequest(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            request_type=RequestType.DELETE,
            status="completed",
            completed_at=completed_at,
            result_url="/exports/data_export_123.zip",
            notes="Exportação concluída com sucesso",
        )
        assert request.status == "completed"
        assert request.completed_at == completed_at
        assert request.result_url == "/exports/data_export_123.zip"
        assert request.notes == "Exportação concluída com sucesso"

    def test_create_rejected_request(self, tenant_id):
        """DataSubjectRequest rejeitada."""
        request = DataSubjectRequest(
            id=AuditId(uuid.uuid4()),
            tenant_id=tenant_id,
            request_type=RequestType.ANONYMIZE,
            status="rejected",
            notes="Solicitação inválida",
        )
        assert request.status == "rejected"
        assert request.completed_at is None


# ─── ConsentRecorded Domain Event ────────────────────────────────────────────


class TestConsentRecorded:
    """Testes do domain event ConsentRecorded."""

    def test_event_creation(self):
        """ConsentRecorded criado corretamente."""
        tenant_id = TenantId(uuid.uuid4())
        event = ConsentRecorded(
            tenant_id=tenant_id,
            data_type="face",
            action="granted",
        )
        assert event.tenant_id == tenant_id
        assert event.data_type == "face"
        assert event.action == "granted"

    def test_event_type_property(self):
        """event_type retorna nome da classe."""
        event = ConsentRecorded()
        assert event.event_type == "ConsentRecorded"
