"""Plugin Fire & Smoke — detecção de incêndio e fumaça."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from analytics.core.plugin_base import AnalyticsPlugin, AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)


class FireSmokePlugin(YOLOPlugin):
    """Plugin de deteco de Fire & Smoke usando modelo YOLO customizado."""

    name = "fire_smoke"
    version = "1.0.0"
    roi_type = "object_in_zone"

    async def initialize(self, config: dict) -> None:
        """Carrega modelo fire.pt."""
        from ultralytics import YOLO

        model_path = config.get("model_path", "/models/fire.pt")
        imgsz = config.get("imgsz", 640)
        self._model = YOLO(model_path)
        self._imgsz = imgsz
        self._conf = config.get("conf", 0.40)
        logger.info("FireSmokePlugin: modelo carregado de %s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame e detecta fire/smoke."""
        detections = self.detect(frame, conf=self._conf)
        if not detections:
            return []

        results = []
        for det in detections:
            class_name = det["class_name"]
            confidence = det["confidence"]
            bbox = det["bbox"]

            matched_roi = None
            if rois:
                for roi in rois:
                    if roi.ia_type == "fire_smoke":
                        if self.point_in_polygon(self.centroid(bbox), roi.polygon_points):
                            matched_roi = roi
                            break

            if matched_roi or not rois:
                payload = {
                    "detection_type": class_name,
                    "confidence": confidence,
                    "bbox": bbox,
                    "severity": "critical" if class_name == "Fire" else "warning",
                }

                result = AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="fire_smoke_detected",
                    payload=payload,
                    occurred_at=datetime.utcnow(),
                    confidence=confidence,
                    roi_id=matched_roi.id if matched_roi else None,
                )
                results.append(result)

        return results
