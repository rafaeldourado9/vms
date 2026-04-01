"""Casos de uso PTZ — orquestra câmera + cliente ONVIF."""
from __future__ import annotations

from vms.cameras.domain import Camera, StreamProtocol
from vms.cameras.repository import CameraRepositoryPort
from vms.core.exceptions import NotFoundError, ValidationError
from vms.ptz.client import PtzClient
from vms.ptz.domain import PtzCapabilities, PtzPreset, PtzVector


class PtzService:
    """Serviço de controle PTZ via ONVIF."""

    def __init__(self, camera_repo: CameraRepositoryPort) -> None:
        self._cameras = camera_repo

    # ── helpers internos ──────────────────────────────────────────────────────

    async def _get_ptz_camera(self, camera_id: str, tenant_id: str) -> Camera:
        """Retorna câmera validando que é ONVIF e suporta PTZ."""
        camera = await self._cameras.get_by_id(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)
        if camera.stream_protocol != StreamProtocol.ONVIF:
            raise ValidationError("PTZ só está disponível para câmeras com protocolo ONVIF")
        if not camera.ptz_supported:
            raise ValidationError("Câmera não tem suporte a PTZ habilitado")
        if not camera.onvif_url:
            raise ValidationError("Câmera não possui onvif_url configurada")
        return camera

    async def _profile_token(self, camera: Camera) -> str:
        """Obtém profile token ONVIF da câmera. Lança ValidationError se não obtido."""
        token = await PtzClient.get_profile_token(
            camera.onvif_url or "",
            camera.onvif_username or "",
            camera.onvif_password or "",
        )
        if not token:
            raise ValidationError("Não foi possível obter profile token ONVIF da câmera")
        return token

    # ── casos de uso ──────────────────────────────────────────────────────────

    async def move(
        self,
        camera_id: str,
        tenant_id: str,
        velocity: PtzVector,
        timeout_seconds: int = 5,
    ) -> None:
        """Inicia movimento contínuo PTZ."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        ok = await PtzClient.continuous_move(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
            velocity=velocity,
            timeout_seconds=timeout_seconds,
        )
        if not ok:
            raise ValidationError("Falha ao executar ContinuousMove na câmera")

    async def absolute_move(
        self,
        camera_id: str,
        tenant_id: str,
        position: PtzVector,
        speed: PtzVector | None = None,
    ) -> None:
        """Move câmera para posição absoluta PTZ."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        ok = await PtzClient.absolute_move(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
            position=position,
            speed=speed,
        )
        if not ok:
            raise ValidationError("Falha ao executar AbsoluteMove na câmera")

    async def stop(self, camera_id: str, tenant_id: str) -> None:
        """Para qualquer movimento PTZ em curso."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        await PtzClient.stop(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
        )

    async def get_presets(self, camera_id: str, tenant_id: str) -> list[PtzPreset]:
        """Retorna lista de presets PTZ salvos na câmera."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        return await PtzClient.get_presets(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
        )

    async def goto_preset(
        self, camera_id: str, tenant_id: str, preset_token: str
    ) -> None:
        """Move câmera para preset salvo pelo token."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        ok = await PtzClient.goto_preset(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
            preset_token=preset_token,
        )
        if not ok:
            raise ValidationError(f"Falha ao ir para preset '{preset_token}'")

    async def save_preset(
        self,
        camera_id: str,
        tenant_id: str,
        preset_name: str,
        preset_token: str | None = None,
    ) -> PtzPreset:
        """Salva posição atual como preset. Retorna preset criado/atualizado."""
        camera = await self._get_ptz_camera(camera_id, tenant_id)
        profile_token = await self._profile_token(camera)
        new_token = await PtzClient.set_preset(
            onvif_url=camera.onvif_url or "",
            username=camera.onvif_username or "",
            password=camera.onvif_password or "",
            profile_token=profile_token,
            preset_name=preset_name,
            preset_token=preset_token,
        )
        if not new_token:
            raise ValidationError("Falha ao salvar preset PTZ na câmera")
        return PtzPreset(token=new_token, name=preset_name)

    async def probe_capabilities(
        self, camera_id: str, tenant_id: str
    ) -> PtzCapabilities:
        """Verifica capacidades PTZ da câmera via ONVIF."""
        camera = await self._cameras.get_by_id(camera_id, tenant_id)
        if not camera:
            raise NotFoundError("Câmera", camera_id)
        if camera.stream_protocol != StreamProtocol.ONVIF or not camera.onvif_url:
            return PtzCapabilities(ptz_supported=False)
        return await PtzClient.get_capabilities(
            camera.onvif_url,
            camera.onvif_username or "",
            camera.onvif_password or "",
        )
