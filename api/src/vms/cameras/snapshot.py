"""Captura de snapshot de câmera — ffmpeg frame capturado inline."""
from __future__ import annotations

import base64
import logging

from vms.cameras.domain import Camera

logger = logging.getLogger(__name__)


async def get_snapshot_url(camera: Camera) -> str | None:
    """
    Captura um frame da câmera e retorna como data URL (data:image/jpeg;base64,...).

    Estratégia:
    1. Tenta HLS interno do MediaMTX (funciona para qualquer câmera com stream ativo)
    2. Para RTSP pull / ONVIF: fallback para RTSP direto
    3. Retorna None se ffmpeg não conseguir capturar frame
    """
    from vms.cameras.thumbnail import capture_thumbnail

    jpeg = await capture_thumbnail(camera)
    if jpeg:
        b64 = base64.b64encode(jpeg).decode()
        return f"data:image/jpeg;base64,{b64}"

    logger.debug("get_snapshot_url: sem frame para camera=%s protocol=%s", camera.id, camera.stream_protocol)
    return None
