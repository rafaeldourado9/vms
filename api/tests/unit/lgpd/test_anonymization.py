"""Testes unitários do AnonymizationService."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vms.lgpd.anonymization import AnonymizationService


class TestAnonymizationService:
    """Testes do AnonymizationService."""

    @pytest.fixture
    def mock_session(self):
        """Sessão mockada."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def svc(self, mock_session):
        return AnonymizationService(mock_session)

    async def test_anonymize_alpr_event_success(self, svc, mock_session):
        """anonymize_alpr_event retorna True em caso de sucesso."""
        event_id = str(uuid.uuid4())
        result = await svc.anonymize_alpr_event(event_id)
        assert result is True
        mock_session.execute.assert_called_once()

    async def test_anonymize_alpr_event_failure(self, svc, mock_session):
        """anonymize_alpr_event retorna False em caso de erro."""
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
        event_id = str(uuid.uuid4())
        result = await svc.anonymize_alpr_event(event_id)
        assert result is False

    async def test_anonymize_face_event_success(self, svc, mock_session):
        """anonymize_face_event retorna True em caso de sucesso."""
        event_id = str(uuid.uuid4())
        result = await svc.anonymize_face_event(event_id)
        assert result is True
        mock_session.execute.assert_called_once()

    async def test_anonymize_face_event_failure(self, svc, mock_session):
        """anonymize_face_event retorna False em caso de erro."""
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
        event_id = str(uuid.uuid4())
        result = await svc.anonymize_face_event(event_id)
        assert result is False

    async def test_delete_event_success(self, svc, mock_session):
        """delete_event retorna True em caso de sucesso."""
        event_id = str(uuid.uuid4())
        result = await svc.delete_event(event_id)
        assert result is True
        mock_session.execute.assert_called_once()

    async def test_delete_event_failure(self, svc, mock_session):
        """delete_event retorna False em caso de erro."""
        mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
        event_id = str(uuid.uuid4())
        result = await svc.delete_event(event_id)
        assert result is False
