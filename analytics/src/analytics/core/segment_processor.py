"""Processador de segmentos de gravação para analytics pós-gravação."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from analytics.core.plugin_base import AnalyticsPlugin, FrameMetadata, ROIConfig

logger = logging.getLogger(__name__)

# Tipos de ROI que só são processados em modo real-time (stream ao vivo)
REALTIME_ONLY_TYPES: frozenset[str] = frozenset({"intrusion"})


class SegmentProcessor:
    """
    Processa segmentos .mp4 gravados para analytics pós-gravação.

    Fluxo:
    1. Lê o .mp4 do disco via OpenCV
    2. Extrai frames a ``fps`` por segundo
    3. Busca ROIs da câmera (ignora tipos realtime-only como intrusão)
    4. Roteia cada frame para os plugins correspondentes
    5. Envia resultados ao VMS API via VMSClient
    """

    def __init__(
        self,
        plugins: dict[str, AnalyticsPlugin],
        vms_client,  # VMSClient — evita import circular
        fps: int = 1,
    ) -> None:
        self._plugins = plugins
        self._vms_client = vms_client
        self._fps = fps

    async def process(
        self,
        segment_id: str,
        file_path: str,
        camera_id: str,
        tenant_id: str,
    ) -> int:
        """
        Processa um segmento .mp4.

        Retorna o número total de eventos gerados.
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning("Arquivo de segmento não encontrado: %s", file_path)
            return 0

        # Busca ROIs — filtra tipos realtime-only
        all_rois: list[ROIConfig] = await self._vms_client.get_camera_rois(camera_id)
        rois = [r for r in all_rois if r.ia_type not in REALTIME_ONLY_TYPES and r.ia_type in self._plugins]

        if not rois:
            logger.debug(
                "Câmera %s sem ROIs pós-gravação ativas — segmento %s ignorado",
                camera_id,
                segment_id,
            )
            return 0

        # Extrai frames em thread executor (cv2 é síncrono)
        loop = asyncio.get_event_loop()
        frames: list[tuple[np.ndarray, datetime]] = await loop.run_in_executor(
            None, self._extract_frames, file_path
        )

        if not frames:
            logger.warning("Nenhum frame extraído de %s", file_path)
            return 0

        events_count = 0
        for frame, frame_ts in frames:
            metadata = FrameMetadata(
                camera_id=camera_id,
                tenant_id=tenant_id,
                timestamp=frame_ts,
                stream_url=f"segment:{segment_id}",
            )
            for roi_type, plugin in self._plugins.items():
                if roi_type in REALTIME_ONLY_TYPES:
                    continue
                matching_rois = [r for r in rois if r.ia_type == roi_type]
                if not matching_rois:
                    continue
                try:
                    results = await plugin.process_frame(frame, metadata, matching_rois)
                    for result in results:
                        payload = {
                            "plugin": result.plugin,
                            "camera_id": result.camera_id,
                            "tenant_id": result.tenant_id,
                            "roi_id": result.roi_id,
                            "event_type": result.event_type,
                            "payload": result.payload,
                            "occurred_at": result.occurred_at.isoformat(),
                        }
                        await self._vms_client.ingest_result(payload)
                        events_count += 1
                except Exception:
                    logger.exception(
                        "Erro no plugin %s ao processar segmento %s",
                        plugin.name,
                        segment_id,
                    )

        logger.info(
            "Segmento %s processado: %d frames, %d eventos (câmera %s)",
            segment_id,
            len(frames),
            events_count,
            camera_id,
        )
        return events_count

    def _extract_frames(self, file_path: str) -> list[tuple[np.ndarray, datetime]]:
        """
        Extrai frames do .mp4 via OpenCV a ``self._fps`` fps.

        Retorna lista de (frame_ndarray, timestamp_utc).
        """
        frames: list[tuple[np.ndarray, datetime]] = []
        cap: cv2.VideoCapture | None = None
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                logger.warning("Não foi possível abrir vídeo: %s", file_path)
                return frames

            video_fps: float = cap.get(cv2.CAP_PROP_FPS) or 25.0
            frame_interval = max(1, round(video_fps / self._fps))

            frame_idx = 0
            capture_start = datetime.now(UTC)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame_idx % frame_interval == 0:
                    # Estima timestamp proporcional à posição no vídeo
                    seconds_offset = frame_idx / video_fps
                    ts = capture_start.replace(
                        second=int(capture_start.second + seconds_offset) % 60,
                        microsecond=0,
                    )
                    frames.append((frame, ts))
                frame_idx += 1
        except Exception:
            logger.exception("Erro ao extrair frames de %s", file_path)
        finally:
            if cap is not None:
                cap.release()
        return frames
