"""Testes unitários do PtzService com mocks do PtzClient ONVIF."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vms.cameras.domain import Camera, CameraManufacturer, StreamProtocol
from vms.core.exceptions import NotFoundError, ValidationError
from vms.ptz.domain import PtzPreset, PtzVector
from vms.ptz.service import PtzService


def _make_camera(**kwargs) -> Camera:
    defaults = dict(
        id="cam-1",
        tenant_id="t1",
        name="Câmera PTZ",
        manufacturer=CameraManufacturer.HIKVISION,
        stream_protocol=StreamProtocol.ONVIF,
        onvif_url="http://192.168.1.100:80/onvif/device_service",
        onvif_username="admin",
        onvif_password="senha123",
        ptz_supported=True,
    )
    defaults.update(kwargs)
    return Camera(**defaults)


@pytest.fixture
def camera_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def svc(camera_repo):
    return PtzService(camera_repo)


# ─── Validações de acesso ──────────────────────────────────────────────────────

class TestPtzServiceValidations:
    async def test_camera_nao_encontrada(self, svc, camera_repo):
        """NotFoundError quando câmera não existe."""
        camera_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await svc.move("cam-x", "t1", PtzVector())

    async def test_camera_nao_onvif(self, svc, camera_repo):
        """ValidationError quando câmera não é ONVIF."""
        camera_repo.get_by_id.return_value = _make_camera(
            stream_protocol=StreamProtocol.RTSP_PULL, ptz_supported=True
        )
        with pytest.raises(ValidationError, match="ONVIF"):
            await svc.move("cam-1", "t1", PtzVector())

    async def test_ptz_nao_habilitado(self, svc, camera_repo):
        """ValidationError quando ptz_supported=False."""
        camera_repo.get_by_id.return_value = _make_camera(ptz_supported=False)
        with pytest.raises(ValidationError, match="suporte"):
            await svc.move("cam-1", "t1", PtzVector())

    async def test_sem_profile_token(self, svc, camera_repo):
        """ValidationError quando câmera não retorna profile token."""
        camera_repo.get_by_id.return_value = _make_camera()
        with patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value=None)):
            with pytest.raises(ValidationError, match="profile token"):
                await svc.move("cam-1", "t1", PtzVector())


# ─── move ─────────────────────────────────────────────────────────────────────

class TestPtzMove:
    async def test_move_ok(self, svc, camera_repo):
        """move() chama ContinuousMove com velocidade correta."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="profile-1")),
            patch("vms.ptz.service.PtzClient.continuous_move", AsyncMock(return_value=True)) as mock_move,
        ):
            velocity = PtzVector(pan=0.5, tilt=0.3, zoom=0.0)
            await svc.move("cam-1", "t1", velocity, timeout_seconds=3)
            mock_move.assert_called_once()
            call_kwargs = mock_move.call_args.kwargs
            assert call_kwargs["velocity"].pan == 0.5
            assert call_kwargs["velocity"].tilt == 0.3
            assert call_kwargs["timeout_seconds"] == 3

    async def test_move_falha_onvif(self, svc, camera_repo):
        """ValidationError quando ContinuousMove retorna False."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.continuous_move", AsyncMock(return_value=False)),
        ):
            with pytest.raises(ValidationError, match="ContinuousMove"):
                await svc.move("cam-1", "t1", PtzVector(pan=1.0))


# ─── stop ─────────────────────────────────────────────────────────────────────

class TestPtzStop:
    async def test_stop_ok(self, svc, camera_repo):
        """stop() chama PtzClient.stop sem erro."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.stop", AsyncMock(return_value=True)) as mock_stop,
        ):
            await svc.stop("cam-1", "t1")
            mock_stop.assert_called_once()


# ─── presets ──────────────────────────────────────────────────────────────────

class TestPtzPresets:
    async def test_get_presets_ok(self, svc, camera_repo):
        """get_presets() retorna lista de presets da câmera."""
        camera_repo.get_by_id.return_value = _make_camera()
        presets = [PtzPreset(token="1", name="Entrada"), PtzPreset(token="2", name="Pátio")]
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.get_presets", AsyncMock(return_value=presets)),
        ):
            result = await svc.get_presets("cam-1", "t1")
            assert len(result) == 2
            assert result[0].name == "Entrada"

    async def test_goto_preset_ok(self, svc, camera_repo):
        """goto_preset() chama GotoPreset com token correto."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.goto_preset", AsyncMock(return_value=True)) as mock_goto,
        ):
            await svc.goto_preset("cam-1", "t1", "preset-3")
            call_kwargs = mock_goto.call_args.kwargs
            assert call_kwargs["preset_token"] == "preset-3"

    async def test_goto_preset_falha(self, svc, camera_repo):
        """ValidationError quando GotoPreset retorna False."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.goto_preset", AsyncMock(return_value=False)),
        ):
            with pytest.raises(ValidationError, match="preset"):
                await svc.goto_preset("cam-1", "t1", "preset-x")

    async def test_save_preset_ok(self, svc, camera_repo):
        """save_preset() retorna PtzPreset com token retornado pela câmera."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.set_preset", AsyncMock(return_value="token-42")),
        ):
            preset = await svc.save_preset("cam-1", "t1", "Nova posição")
            assert preset.token == "token-42"
            assert preset.name == "Nova posição"

    async def test_save_preset_falha(self, svc, camera_repo):
        """ValidationError quando SetPreset retorna None."""
        camera_repo.get_by_id.return_value = _make_camera()
        with (
            patch("vms.ptz.service.PtzClient.get_profile_token", AsyncMock(return_value="p1")),
            patch("vms.ptz.service.PtzClient.set_preset", AsyncMock(return_value=None)),
        ):
            with pytest.raises(ValidationError, match="preset"):
                await svc.save_preset("cam-1", "t1", "Falha")


# ─── probe_capabilities ───────────────────────────────────────────────────────

class TestPtzProbeCapabilities:
    async def test_probe_camera_nao_onvif(self, svc, camera_repo):
        """Câmera não-ONVIF retorna ptz_supported=False sem chamar ONVIF."""
        camera_repo.get_by_id.return_value = _make_camera(
            stream_protocol=StreamProtocol.RTSP_PULL
        )
        caps = await svc.probe_capabilities("cam-1", "t1")
        assert caps.ptz_supported is False

    async def test_probe_suporte_detectado(self, svc, camera_repo):
        """probe_capabilities retorna PtzCapabilities correto da câmera ONVIF."""
        from vms.ptz.domain import PtzCapabilities
        camera_repo.get_by_id.return_value = _make_camera()
        caps_mock = PtzCapabilities(
            ptz_supported=True,
            can_continuous_move=True,
            can_absolute_move=True,
        )
        with patch("vms.ptz.service.PtzClient.get_capabilities", AsyncMock(return_value=caps_mock)):
            caps = await svc.probe_capabilities("cam-1", "t1")
            assert caps.ptz_supported is True
            assert caps.can_continuous_move is True
