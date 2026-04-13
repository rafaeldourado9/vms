"""Plugin de detecção de intrusão — YOLOv8n + polígono."""
from __future__ import annotations

import logging
import time

import numpy as np

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)


class IntrusionDetectionPlugin(YOLOPlugin):
    """
    Detecta presença de objetos (padrão: pessoa) dentro de uma ROI.

    Gerenciamento de estado de presença:
    - intruder.started: intruso entrou na ROI
    - intruder.ongoing: intruso ainda presente (a cada N s)
    - intruder.cleared: intruso saiu da ROI

    Lógica:
    1. Inferência YOLO no frame completo
    2. Filtra pelas classes configuradas na ROI
    3. Para cada ROI, verifica se centroide da bbox está dentro do polígono
    4. Emite evento.started quando intruso detectado
    5. Emite evento.ongoing se intruso permanece (a cada ongoing_interval)
    6. Emite evento.cleared quando intruso some por > grace_frames
    """

    name = "intrusion_detection"
    version = "1.0.0"
    roi_type = "intrusion"

    def __init__(self) -> None:
        super().__init__()
        # Cooldown por ROI: {roi_id: last_emit_timestamp}
        self._cooldowns: dict[str, float] = {}
        # Estado de presença por ROI: {roi_id: {"detected_at": float, "last_seen": float, "count": int}}
        self._active_intrusions: dict[str, dict] = {}
        self._ongoing_interval: float = 30.0  # segundos entre eventos ongoing
        self._grace_frames: int = 10  # frames sem detecção antes de "cleared"
        self._frame_counts: dict[str, int] = {}

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame para detecção de intrusão (modo standalone)."""
        results: list[AnalyticsResult] = []

        # Coleta todas as classes necessárias de todas as ROIs
        all_classes: set[int] = set()
        for roi in rois:
            classes = roi.config.get("classes", [0])  # padrão: person
            all_classes.update(classes)

        min_conf = min(
            (roi.config.get("min_confidence", 0.5) for roi in rois),
            default=0.5,
        )

        # Inferência uma vez para todas as ROIs
        detections = self.detect(
            frame,
            conf=min_conf,
            classes=list(all_classes),
        )

        return self._process_detections(detections, rois, metadata, min_conf)

    async def process_shared_frame(
        self,
        detections: list[dict],
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame com detecções pré-computadas (shared inference)."""
        min_conf = min(
            (roi.config.get("min_confidence", 0.5) for roi in rois),
            default=0.5,
        )
        return self._process_detections(detections, rois, metadata, min_conf)

    def _process_detections(
        self,
        detections: list[dict],
        rois: list[ROIConfig],
        metadata: FrameMetadata,
        min_conf: float,
    ) -> list[AnalyticsResult]:
        """Lógica comum de processamento de detecções com estado de presença."""
        results: list[AnalyticsResult] = []

        import time
        now = time.monotonic()

        for roi in rois:
            roi_classes = set(roi.config.get("classes", [0]))
            roi_conf = roi.config.get("min_confidence", 0.5)

            # Filtra por classes e confiança desta ROI
            roi_detections = [
                d for d in detections
                if d["class_id"] in roi_classes and d["confidence"] >= roi_conf
            ]

            # Filtra por polígono
            in_roi = self.filter_in_roi(roi_detections, roi.polygon_points)
            has_intrusion = len(in_roi) > 0

            # Atualizar frame count para grace period
            self._frame_counts[roi.id] = self._frame_counts.get(roi.id, 0) + 1

            if has_intrusion:
                # Reset grace count
                self._frame_counts[roi.id] = 0

                if roi.id not in self._active_intrusions:
                    # Novo intruso → evento.started
                    self._active_intrusions[roi.id] = {
                        "detected_at": now,
                        "last_seen": now,
                        "count": 1,
                    }
                    self._cooldowns[roi.id] = now  # Reset cooldown
                    results.append(self._make_result(
                        roi, in_roi, metadata, "analytics.intrusion.started", now
                    ))
                else:
                    # Intruso ainda presente → verificar ongoing
                    intrusion = self._active_intrusions[roi.id]
                    intrusion["last_seen"] = now
                    intrusion["count"] += 1

                    # Evento ongoing a cada N segundos
                    if now - self._cooldowns.get(roi.id, 0) >= self._ongoing_interval:
                        self._cooldowns[roi.id] = now
                        results.append(self._make_result(
                            roi, in_roi, metadata, "analytics.intrusion.ongoing", now
                        ))
            else:
                # Sem detecção → verificar grace period
                if roi.id in self._active_intrusions:
                    grace_count = self._frame_counts.get(roi.id, 0)
                    if grace_count >= self._grace_frames:
                        # Intruso saiu → evento.cleared
                        intrusion = self._active_intrusions.pop(roi.id)
                        self._cooldowns.pop(roi.id, None)
                        results.append(self._make_result(
                            roi, [], metadata, "analytics.intrusion.cleared", now
                        ))

        return results

    def _make_result(
        self,
        roi: ROIConfig,
        detections: list[dict],
        metadata: FrameMetadata,
        event_type: str,
        now: float,
    ) -> AnalyticsResult:
        """Cria AnalyticsResult com payload padronizado."""
        return AnalyticsResult(
            plugin=self.name,
            camera_id=metadata.camera_id,
            tenant_id=metadata.tenant_id,
            roi_id=roi.id,
            event_type=event_type,
            payload={
                "roi_id": roi.id,
                "roi_name": roi.name,
                "detection_count": len(detections),
                "event_subtype": event_type.split(".")[-1],  # started, ongoing, cleared
                "detections": [
                    {
                        "class": d["class_name"],
                        "confidence": round(d["confidence"], 2),
                        "bbox": d["bbox"],
                    }
                    for d in detections
                ],
            },
            occurred_at=metadata.timestamp,
        )
