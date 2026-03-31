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

    Lógica:
    1. Inferência YOLO no frame completo
    2. Filtra pelas classes configuradas na ROI
    3. Para cada ROI, verifica se centroide da bbox está dentro do polígono
    4. Emite evento se houver detecção, respeitando cooldown
    """

    name = "intrusion_detection"
    version = "1.0.0"
    roi_type = "intrusion"

    def __init__(self) -> None:
        super().__init__()
        # Cooldown por ROI: {roi_id: last_emit_timestamp}
        self._cooldowns: dict[str, float] = {}

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame para detecção de intrusão em cada ROI."""
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

        if not detections:
            return results

        now = time.monotonic()

        for roi in rois:
            cooldown = roi.config.get("cooldown_seconds", 30)
            last_emit = self._cooldowns.get(roi.id, 0.0)
            if now - last_emit < cooldown:
                continue

            roi_classes = set(roi.config.get("classes", [0]))
            roi_conf = roi.config.get("min_confidence", 0.5)

            # Filtra por classes e confiança desta ROI
            roi_detections = [
                d for d in detections
                if d["class_id"] in roi_classes and d["confidence"] >= roi_conf
            ]

            # Filtra por polígono
            in_roi = self.filter_in_roi(roi_detections, roi.polygon_points)

            if in_roi:
                self._cooldowns[roi.id] = now
                results.append(
                    AnalyticsResult(
                        plugin=self.name,
                        camera_id=metadata.camera_id,
                        tenant_id=metadata.tenant_id,
                        roi_id=roi.id,
                        event_type="analytics.intrusion.detected",
                        payload={
                            "roi_id": roi.id,
                            "roi_name": roi.name,
                            "detection_count": len(in_roi),
                            "detections": [
                                {
                                    "class": d["class_name"],
                                    "confidence": round(d["confidence"], 2),
                                    "bbox": d["bbox"],
                                }
                                for d in in_roi
                            ],
                        },
                        occurred_at=metadata.timestamp,
                    )
                )

        return results
