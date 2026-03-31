"""Testes unitários do dispatcher de webhooks com HMAC-SHA256."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from vms.notifications.dispatcher import dispatch_webhook
from vms.notifications.domain import NotificationRule, NotificationStatus


def _make_rule(**overrides) -> NotificationRule:
    defaults = {
        "id": "rule-001",
        "tenant_id": "t1",
        "name": "Test Rule",
        "event_type_pattern": "alpr.*",
        "destination_url": "https://example.com/hook",
        "webhook_secret": "test-secret",
    }
    defaults.update(overrides)
    return NotificationRule(**defaults)


class TestDispatchWebhook:
    """Testes do dispatch de webhook HTTP."""

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    async def test_success_dispatch(self, mock_client_cls):
        """Dispatch com sucesso retorna log SUCCESS."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        rule = _make_rule()
        log = await dispatch_webhook(rule, "alpr.detected", "evt-001", {"plate": "ABC"})

        assert log.status == NotificationStatus.SUCCESS
        assert log.response_code == 200
        assert log.rule_id == "rule-001"
        assert log.vms_event_id == "evt-001"

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    async def test_failed_dispatch_non_2xx(self, mock_client_cls):
        """Dispatch com resposta não-2xx retorna FAILED."""
        mock_response = AsyncMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        log = await dispatch_webhook(_make_rule(), "alpr.detected", "evt-001", {})

        assert log.status == NotificationStatus.FAILED
        assert log.response_code == 500

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    async def test_network_error_returns_failed(self, mock_client_cls):
        """Erro de rede retorna log FAILED sem response_code."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        log = await dispatch_webhook(_make_rule(), "alpr.detected", "evt-001", {})

        assert log.status == NotificationStatus.FAILED
        assert log.response_code is None
        assert "Connection refused" in log.response_body

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    async def test_request_includes_hmac_signature(self, mock_client_cls):
        """Request inclui header X-VMS-Signature com HMAC-SHA256."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await dispatch_webhook(_make_rule(), "alpr.detected", "evt-001", {})

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs[1]["headers"]
        assert "X-VMS-Signature" in headers
        assert headers["X-VMS-Signature"].startswith("sha256=")

    @patch("vms.notifications.dispatcher.httpx.AsyncClient")
    async def test_request_includes_event_type_header(self, mock_client_cls):
        """Request inclui header X-VMS-Event."""
        mock_response = AsyncMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.text = "ok"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await dispatch_webhook(_make_rule(), "camera.online", "evt-002", {})

        headers = mock_client.post.call_args[1]["headers"]
        assert headers["X-VMS-Event"] == "camera.online"
