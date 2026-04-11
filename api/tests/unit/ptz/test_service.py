"""Testes unitários do PtzService — ONVIF PTZ client mockado."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vms.cameras.domain import Camera, CameraManufacturer, StreamProtocol
from vms.cameras.ptz.domain import PtzCommand, PtzPreset
from vms.cameras.ptz.service import PtzService
from vms.core.exceptions import NotFoundError, ValidationError


def _onvif_camera(ptz_supported: bool = True) -> Camera:
    """Câmera ONVIF para usar nos testes."""
    return Camera(
        id="cam-1",
        tenant_id="tenant-1",
        name="PTZ Cam",
        manufacturer=CameraManufacturer.HIKVISION,
        stream_protocol=StreamProtocol.ONVIF,
        onvif_url="http://192.168.1.10/onvif/device_service",
        onvif_username="admin",
        onvif_password="pass",
        ptz_supported=ptz_supported,
    )


def _rtsp_camera() -> Camera:
    """Câmera RTSP (sem PTZ) para testar validação."""
    return Camera(
        id="cam-2",
        tenant_id="tenant-1",
        name="RTSP Cam",
        manufacturer=CameraManufacturer.GENERIC,
        stream_protocol=StreamProtocol.RTSP_PULL,
        rtsp_url="rtsp://192.168.1.20/stream",
    )


@pytest.fixture
def camera_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def svc(camera_repo):
    return PtzService(camera_repo)


class TestPtzServiceListPresets:
    """Testes de list_presets."""

    async def test_list_presets_returns_presets(self, svc, camera_repo):
        """list_presets retorna lista de presets da câmera."""
        camera_repo.get_by_id.return_value = _onvif_camera()
        expected = [PtzPreset(token="1", name="Entrada"), PtzPreset(token="2", name="Pátio")]

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.get_presets", new=AsyncMock(return_value=expected)),
        ):
            result = await svc.list_presets("cam-1", "tenant-1")

        assert result == expected

    async def test_list_presets_empty_when_none_saved(self, svc, camera_repo):
        """list_presets retorna lista vazia se câmera não tem presets."""
        camera_repo.get_by_id.return_value = _onvif_camera()

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.get_presets", new=AsyncMock(return_value=[])),
        ):
            result = await svc.list_presets("cam-1", "tenant-1")

        assert result == []

    async def test_list_presets_raises_not_found(self, svc, camera_repo):
        """list_presets lança NotFoundError se câmera não existe."""
        camera_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await svc.list_presets("cam-999", "tenant-1")

    async def test_list_presets_raises_for_non_onvif(self, svc, camera_repo):
        """list_presets lança ValidationError para câmera não-ONVIF."""
        camera_repo.get_by_id.return_value = _rtsp_camera()
        with pytest.raises(ValidationError):
            await svc.list_presets("cam-2", "tenant-1")


class TestPtzServiceGotoPreset:
    """Testes de goto_preset."""

    async def test_goto_preset_calls_client(self, svc, camera_repo):
        """goto_preset chama PtzClient.goto_preset com parâmetros corretos."""
        camera_repo.get_by_id.return_value = _onvif_camera()
        mock_goto = AsyncMock()

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.goto_preset", new=mock_goto),
        ):
            await svc.goto_preset("cam-1", "tenant-1", "preset-token-1", speed=0.8)

        mock_goto.assert_called_once()
        call_kwargs = mock_goto.call_args
        assert call_kwargs.args[2] == "preset-token-1"
        assert call_kwargs.args[3] == 0.8

    async def test_goto_preset_raises_for_non_onvif(self, svc, camera_repo):
        """goto_preset lança ValidationError para câmera não-ONVIF."""
        camera_repo.get_by_id.return_value = _rtsp_camera()
        with pytest.raises(ValidationError):
            await svc.goto_preset("cam-2", "tenant-1", "preset-1")


class TestPtzServiceMove:
    """Testes de move (ContinuousMove)."""

    async def test_move_calls_continuous_move(self, svc, camera_repo):
        """move chama PtzClient.continuous_move com o PtzCommand correto."""
        camera_repo.get_by_id.return_value = _onvif_camera()
        mock_move = AsyncMock()
        command = PtzCommand(pan=0.5, tilt=-0.3, zoom=0.0, speed=0.7)

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.continuous_move", new=mock_move),
        ):
            await svc.move("cam-1", "tenant-1", command)

        mock_move.assert_called_once()
        passed_command = mock_move.call_args.args[2]
        assert passed_command.pan == 0.5
        assert passed_command.tilt == -0.3

    async def test_move_raises_for_non_onvif(self, svc, camera_repo):
        """move lança ValidationError para câmera não-ONVIF."""
        camera_repo.get_by_id.return_value = _rtsp_camera()
        with pytest.raises(ValidationError):
            await svc.move("cam-2", "tenant-1", PtzCommand())


class TestPtzServiceStop:
    """Testes de stop."""

    async def test_stop_calls_client(self, svc, camera_repo):
        """stop chama PtzClient.stop."""
        camera_repo.get_by_id.return_value = _onvif_camera()
        mock_stop = AsyncMock()

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.stop", new=mock_stop),
        ):
            await svc.stop("cam-1", "tenant-1")

        mock_stop.assert_called_once()

    async def test_stop_raises_not_found(self, svc, camera_repo):
        """stop lança NotFoundError se câmera não existe."""
        camera_repo.get_by_id.return_value = None
        with pytest.raises(NotFoundError):
            await svc.stop("cam-999", "tenant-1")


class TestPtzServiceSavePreset:
    """Testes de save_preset."""

    async def test_save_preset_returns_preset(self, svc, camera_repo):
        """save_preset retorna PtzPreset com token e nome."""
        camera_repo.get_by_id.return_value = _onvif_camera()

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch("vms.cameras.ptz.service.PtzClient.set_preset", new=AsyncMock(return_value="new-token-42")),
        ):
            result = await svc.save_preset("cam-1", "tenant-1", "Portaria")

        assert result.token == "new-token-42"
        assert result.name == "Portaria"

    async def test_save_preset_raises_for_non_onvif(self, svc, camera_repo):
        """save_preset lança ValidationError para câmera não-ONVIF."""
        camera_repo.get_by_id.return_value = _rtsp_camera()
        with pytest.raises(ValidationError):
            await svc.save_preset("cam-2", "tenant-1", "Preset")

    async def test_save_preset_propagates_client_error(self, svc, camera_repo):
        """save_preset propaga ValidationError lançado pelo PtzClient."""
        camera_repo.get_by_id.return_value = _onvif_camera()

        with (
            patch("vms.cameras.ptz.service.PtzClient.get_ptz_url", new=AsyncMock(return_value="http://cam/ptz")),
            patch("vms.cameras.ptz.service.PtzClient.get_profile_token", new=AsyncMock(return_value="prof-1")),
            patch(
                "vms.cameras.ptz.service.PtzClient.set_preset",
                new=AsyncMock(side_effect=ValidationError("SetPreset falhou: HTTP 500")),
            ),
        ):
            with pytest.raises(ValidationError, match="SetPreset falhou"):
                await svc.save_preset("cam-1", "tenant-1", "Preset")
