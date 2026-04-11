"""Plugin Horse Cart — detecção de cavalos e carroças."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)


class HorseCartPlugin(YOLOPlugin):
    """Plugin de detecção de cavalos e carroças."""

    name = "horse_cart"
    version = "1.0.0"
    roi_type = "object_in_zone"

    async def initialize(self, config: dict) -> None:
        """Carrega modelo horse_cart.pt (best_v3.pt)."""
        from ultralytics import YOLO

        model_path = config.get("model_path", "/models/horse_cart.pt")
        imgsz = config.get("imgsz", 640)
        self._model = YOLO(model_path)
        self._imgsz = imgsz
        self._conf = config.get("conf", 0.35)
        logger.info("HorseCartPlugin: modelo carregado de %s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame e detecta horses/carts."""
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
                    if roi.ia_type == "horse_cart":
                        if self.point_in_polygon(self.centroid(bbox), roi.polygon_points):
                            matched_roi = roi
                            break

            if matched_roi or not rois:
                payload = {
                    "object_type": class_name,
                    "confidence": confidence,
                    "bbox": bbox,
                    "severity": "info",
                }

                result = AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="horse_cart_detected",
                    payload=payload,
                    occurred_at=datetime.utcnow(),
                    confidence=confidence,
                    roi_id=matched_roi.id if matched_roi else None,
                )
                results.append(result)

        return results
