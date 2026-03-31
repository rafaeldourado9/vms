"""Captura de snapshot de câmera — ONVIF GetSnapshotUri ou ffmpeg frame."""
from __future__ import annotations

from vms.cameras.domain import Camera, StreamProtocol


async def get_snapshot_url(camera: Camera) -> str | None:
    """
    Retorna URL de snapshot para a câmera.

    - ONVIF: usa snapshot_url extraída via GetSnapshotUri (se disponível)
    - rtsp_pull / onvif com rtsp_url: gera URL de snapshot via proxy interno
    - rtmp_push: retorna None (snapshot não disponível sem stream ativo)
    """
    if camera.stream_protocol == StreamProtocol.ONVIF:
        # Faz probe rápido para obter snapshot URL
        if camera.onvif_url and camera.onvif_username:
            from vms.cameras.onvif_client import OnvifClient
            result = await OnvifClient.probe(
                camera.onvif_url,
                camera.onvif_username or "",
                camera.onvif_password or "",
                timeout=3.0,
            )
            if result.snapshot_url:
                return result.snapshot_url

    if camera.rtsp_url:
        # Retorna URL do endpoint interno que captura frame via ffmpeg
        # O endpoint /streaming/snapshot/{path} é servido pelo FastAPI
        return f"/streaming/snapshot/{camera.mediamtx_path}"

    return None
