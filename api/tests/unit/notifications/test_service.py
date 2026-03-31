"""Testes unitários do NotificationService."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vms.core.exceptions import NotFoundError
from vms.notifications.domain import (
    NotificationLog,
    NotificationRule,
    NotificationStatus,
)
from vms.notifications.service import NotificationService


def _make_rule(**overrides) -> NotificationRule:
    defaults = {
        "id": "rule-001",
        "tenant_id": "t1",
        "name": "ALPR Alert",
        "event_type_pattern": "alpr.*",
        "destination_url": "https://example.com/webhook",
        "webhook_secret": "secret123",
        "is_active": True,
    }
    defaults.update(overrides)
    return NotificationRule(**defaults)


def _make_log(**overrides) -> NotificationLog:
    defaults = {
        "id": "log-001",
        "tenant_id": "t1",
        "rule_id": "rule-001",
        "vms_event_id": "evt-001",
        "status": NotificationStatus.SUCCESS,
        "response_code": 200,
    }
    defaults.update(overrides)
    return NotificationLog(**defaults)


@pytest.fixture
def rule_repo():
    repo = AsyncMock()
    repo.create = AsyncMock(side_effect=lambda r: r)
    repo.list_by_tenant = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def log_repo():
    repo = AsyncMock()
    repo.create = AsyncMock(side_effect=lambda l: l)
    return repo


@pytest.fixture
def svc(rule_repo, log_repo):
    return NotificationService(rule_repo, log_repo)


class TestNotificationServiceRules:
    """Testes de CRUD de regras."""

    async def test_create_rule(self, svc, rule_repo):
        """Cria regra com dados corretos."""
        result = await svc.create_rule(
            "t1", "Test Rule", "alpr.*", "https://example.com/hook", "s3cret",
        )
        assert result.tenant_id == "t1"
        assert result.name == "Test Rule"
        assert result.event_type_pattern == "alpr.*"
        rule_repo.create.assert_called_once()

    async def test_list_rules(self, svc, rule_repo):
        """Lista regras do tenant."""
        rules = [_make_rule(id="r1"), _make_rule(id="r2")]
        rule_repo.list_by_tenant = AsyncMock(return_value=rules)

        result = await svc.list_rules("t1")

        assert len(result) == 2
        rule_repo.list_by_tenant.assert_called_once_with("t1", active_only=False)

    async def test_get_rule_found(self, svc, rule_repo):
        """Retorna regra quando encontrada."""
        rule_repo.get_by_id = AsyncMock(return_value=_make_rule())
        result = await svc.get_rule("rule-001", "t1")
        assert result.id == "rule-001"

    async def test_get_rule_not_found_raises(self, svc, rule_repo):
        """Lança NotFoundError quando regra não existe."""
        rule_repo.get_by_id = AsyncMock(return_value=None)
        with pytest.raises(NotFoundError):
            await svc.get_rule("nonexistent", "t1")

    async def test_delete_rule(self, svc, rule_repo):
        """Deleta regra existente sem erro."""
        await svc.delete_rule("rule-001", "t1")
        rule_repo.delete.assert_called_once_with("rule-001", "t1")

    async def test_delete_rule_not_found_raises(self, svc, rule_repo):
        """Lança NotFoundError ao deletar regra inexistente."""
        rule_repo.delete = AsyncMock(return_value=False)
        with pytest.raises(NotFoundError):
            await svc.delete_rule("nonexistent", "t1")


class TestNotificationServiceDispatch:
    """Testes de evaluate_and_dispatch."""

    @patch("vms.notifications.service.dispatch_webhook", new_callable=AsyncMock)
    async def test_dispatch_matching_rules(
        self, mock_dispatch, svc, rule_repo, log_repo
    ):
        """Dispara webhook para regras que casam com o event_type."""
        rule = _make_rule(event_type_pattern="alpr.*")
        rule_repo.list_by_tenant = AsyncMock(return_value=[rule])
        mock_dispatch.return_value = _make_log()

        logs = await svc.evaluate_and_dispatch(
            "t1", "alpr.detected", "evt-001", {"plate": "ABC1D23"},
        )

        assert len(logs) == 1
        mock_dispatch.assert_called_once()
        log_repo.create.assert_called_once()

    @patch("vms.notifications.service.dispatch_webhook", new_callable=AsyncMock)
    async def test_no_dispatch_when_no_match(
        self, mock_dispatch, svc, rule_repo
    ):
        """Nenhum webhook disparado se nenhuma regra casa."""
        rule = _make_rule(event_type_pattern="camera.*")
        rule_repo.list_by_tenant = AsyncMock(return_value=[rule])

        logs = await svc.evaluate_and_dispatch(
            "t1", "alpr.detected", "evt-001", {},
        )

        assert len(logs) == 0
        mock_dispatch.assert_not_called()

    @patch("vms.notifications.service.dispatch_webhook", new_callable=AsyncMock)
    async def test_dispatch_multiple_matching_rules(
        self, mock_dispatch, svc, rule_repo, log_repo
    ):
        """Dispara webhook para todas as regras que casam."""
        rules = [
            _make_rule(id="r1", event_type_pattern="alpr.*"),
            _make_rule(id="r2", event_type_pattern="*"),
            _make_rule(id="r3", event_type_pattern="camera.*"),
        ]
        rule_repo.list_by_tenant = AsyncMock(return_value=rules)
        mock_dispatch.return_value = _make_log()

        logs = await svc.evaluate_and_dispatch(
            "t1", "alpr.detected", "evt-001", {},
        )

        # r1 (alpr.*) and r2 (*) match, r3 (camera.*) does not
        assert len(logs) == 2
        assert mock_dispatch.call_count == 2
