"""Testes unitários da lógica de retenção pendente (upgrade/downgrade)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from vms.cameras.domain import Camera, CameraManufacturer, StreamProtocol
from vms.cameras.service import CameraService, _apply_retention_change


def _make_camera(retention_days: int = 7, **kwargs) -> Camera:
    defaults = dict(
        id="cam-1",
        tenant_id="t1",
        name="Câmera Teste",
        manufacturer=CameraManufacturer.GENERIC,
        stream_protocol=StreamProtocol.RTSP_PULL,
        rtsp_url="rtsp://x",
        retention_days=retention_days,
    )
    defaults.update(kwargs)
    return Camera(**defaults)


# ─── _apply_retention_change (função pura) ────────────────────────────────────

class TestApplyRetentionChange:
    def test_upgrade_agenda_pending(self):
        """Upgrade cria retention_days_pending sem alterar retention_days."""
        cam = _make_camera(retention_days=5)
        _apply_retention_change(cam, 15)

        assert cam.retention_days == 5           # mantém atual
        assert cam.retention_days_pending == 15  # agenda novo
        assert cam.retention_pending_from is not None
        # deve ser em ~5 dias a partir de agora
        delta = cam.retention_pending_from - datetime.now(UTC)
        assert timedelta(days=4, hours=23) < delta < timedelta(days=5, hours=1)

    def test_downgrade_aplica_imediatamente(self):
        """Downgrade aplica imediatamente e limpa qualquer pending."""
        cam = _make_camera(retention_days=15)
        cam.retention_days_pending = 20
        cam.retention_pending_from = datetime.now(UTC) + timedelta(days=10)

        _apply_retention_change(cam, 5)

        assert cam.retention_days == 5
        assert cam.retention_days_pending is None
        assert cam.retention_pending_from is None

    def test_mesmo_valor_sem_efeito(self):
        """Alterar para o mesmo valor não muda nada."""
        cam = _make_camera(retention_days=7)
        _apply_retention_change(cam, 7)

        assert cam.retention_days == 7
        assert cam.retention_days_pending is None
        assert cam.retention_pending_from is None

    def test_upgrade_sobre_pending_existente(self):
        """Upgrade quando já há um pending substitui o pending anterior."""
        cam = _make_camera(retention_days=5)
        cam.retention_days_pending = 10
        cam.retention_pending_from = datetime.now(UTC) + timedelta(days=3)

        _apply_retention_change(cam, 15)

        assert cam.retention_days_pending == 15  # atualiza para o novo
        assert cam.retention_days == 5           # atual não muda


# ─── CameraService.update_camera — retention logic ────────────────────────────

class TestUpdateCameraRetention:
    @pytest.fixture
    def camera_repo(self):
        repo = AsyncMock()
        repo.update = AsyncMock(side_effect=lambda c: c)
        return repo

    @pytest.fixture
    def svc(self, camera_repo):
        return CameraService(camera_repo)

    async def test_update_retention_upgrade_via_service(self, svc, camera_repo):
        """update_camera com upgrade agenda pending corretamente."""
        cam = _make_camera(retention_days=5)
        camera_repo.get_by_id = AsyncMock(return_value=cam)

        updated = await svc.update_camera("cam-1", "t1", retention_days=15)

        assert updated.retention_days == 5
        assert updated.retention_days_pending == 15
        camera_repo.update.assert_called_once()

    async def test_update_retention_downgrade_via_service(self, svc, camera_repo):
        """update_camera com downgrade aplica imediatamente."""
        cam = _make_camera(retention_days=15)
        camera_repo.get_by_id = AsyncMock(return_value=cam)

        updated = await svc.update_camera("cam-1", "t1", retention_days=5)

        assert updated.retention_days == 5
        assert updated.retention_days_pending is None
