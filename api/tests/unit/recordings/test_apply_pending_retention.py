"""Testes unitários da ARQ task apply_pending_retention."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vms.recordings.tasks import task_apply_pending_retention


class TestApplyPendingRetentionTask:
    """Testes da task ARQ que aplica retenção pendente."""

    async def test_aplica_cameras_com_pending_vencido(self):
        """Câmeras com retention_pending_from no passado são atualizadas."""
        # Simula 2 câmeras com pending vencido
        cam1 = MagicMock(id="cam-1", retention_days_pending=15)
        cam2 = MagicMock(id="cam-2", retention_days_pending=10)

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=AsyncMock(all=lambda: [cam1, cam2]))
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"redis": AsyncMock()}

        with patch("vms.recordings.tasks.get_session_factory", return_value=mock_factory):
            await task_apply_pending_retention(ctx)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_sem_cameras_pendentes_nao_executa_update(self):
        """Quando não há câmeras com pending, não executa UPDATE."""
        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=AsyncMock(all=lambda: []))
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"redis": AsyncMock()}

        with patch("vms.recordings.tasks.get_session_factory", return_value=mock_factory):
            await task_apply_pending_retention(ctx)

        mock_session.execute.assert_not_called()
        mock_session.commit.assert_not_called()

    async def test_erro_faz_rollback(self):
        """Erros internos fazem rollback sem propagar."""
        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_session.rollback = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        ctx = {"redis": AsyncMock()}

        with patch("vms.recordings.tasks.get_session_factory", return_value=mock_factory):
            # Não deve propagar exceção
            await task_apply_pending_retention(ctx)

        mock_session.rollback.assert_called_once()
