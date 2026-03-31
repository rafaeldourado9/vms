"""Testes unitários — geração e verificação de viewer tokens."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from vms.streaming.service import StreamingService


def _svc(**kwargs) -> StreamingService:
    return StreamingService(
        repo=AsyncMock(),
        camera_repo=kwargs.get("camera_repo"),
        api_key_repo=kwargs.get("api_key_repo"),
    )


class TestVerifyViewerToken:
    """Testes de StreamingService.verify_viewer_token."""

    async def test_valid_viewer_token_accepted(self):
        """Token JWT de tipo 'viewer' com camera_id correto é aceito."""
        from vms.core.security import create_viewer_token

        token = create_viewer_token(camera_id="c1", tenant_id="t1")
        svc = _svc()
        result = await svc.verify_viewer_token(token, "tenant-t1/cam-c1")
        assert result is True

    async def test_empty_token_rejected(self):
        """Token vazio é rejeitado."""
        svc = _svc()
        result = await svc.verify_viewer_token("", "tenant-t1/cam-c1")
        assert result is False

    async def test_wrong_camera_id_rejected(self):
        """Token com camera_id diferente do path é rejeitado."""
        from vms.core.security import create_viewer_token

        token = create_viewer_token(camera_id="c2", tenant_id="t1")
        svc = _svc()
        result = await svc.verify_viewer_token(token, "tenant-t1/cam-c1")
        assert result is False

    async def test_non_viewer_token_rejected(self):
        """Token de acesso (não viewer) é rejeitado."""
        from vms.core.security import create_access_token

        token = create_access_token(subject="user-1", tenant_id="t1", role="operator")
        svc = _svc()
        result = await svc.verify_viewer_token(token, "tenant-t1/cam-c1")
        assert result is False

    async def test_invalid_token_rejected(self):
        """Token malformado é rejeitado."""
        svc = _svc()
        result = await svc.verify_viewer_token("not.a.token", "tenant-t1/cam-c1")
        assert result is False

    async def test_invalid_path_rejected(self):
        """Path inválido (não segue padrão tenant-x/cam-y) é rejeitado."""
        from vms.core.security import create_viewer_token

        token = create_viewer_token(camera_id="c1", tenant_id="t1")
        svc = _svc()
        result = await svc.verify_viewer_token(token, "invalid-path")
        assert result is False
