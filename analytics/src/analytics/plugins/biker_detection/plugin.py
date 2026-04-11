"""Plugin Biker Detection — detecção de motociclistas com/sem capacete."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)


class BikerDetectionPlugin(YOLOPlugin):
    """Plugin de detecção de motociclistas (com/sem capacete)."""

    name = "biker_detection"
    version = "1.0.0"
    roi_type = "object_in_zone"

    async def initialize(self, config: dict) -> None:
        """Carrega modelo biker_2.pt."""
        from ultralytics import YOLO

        model_path = config.get("model_path", "/models/biker_2.pt")
        imgsz = config.get("imgsz", 640)
        self._model = YOLO(model_path)
        self._imgsz = imgsz
        self._conf = config.get("conf", 0.40)
        logger.info("BikerDetectionPlugin: modelo carregado de %s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame e detecta bikers com/sem capacete."""
        detections = self.detect(frame, conf=self._conf)
        if not detections:
            return []

        results = []
        for det in detections:
            class_name = det["class_name"]
            confidence = det["confidence"]
            bbox = det["bbox"]

            is_violation = class_name == "WO_Helmet"

            matched_roi = None
            if rois:
                for roi in rois:
                    if roi.ia_type == "biker":
                        if self.point_in_polygon(self.centroid(bbox), roi.polygon_points):
                            matched_roi = roi
                            break

            if matched_roi or not rois:
                payload = {
                    "biker_type": class_name,
                    "confidence": confidence,
                    "bbox": bbox,
                    "has_helmet": not is_violation,
                    "severity": "critical" if is_violation else "info",
                }

                result = AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="biker_no_helmet" if is_violation else "biker_detected",
                    payload=payload,
                    occurred_at=datetime.utcnow(),
                    confidence=confidence,
                    roi_id=matched_roi.id if matched_roi else None,
                )
                results.append(result)

        return results
