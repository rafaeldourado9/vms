"""Plugin PPE Detection — detecção de EPIs (capacete, colete)."""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)


class PPEDetectionPlugin(YOLOPlugin):
    """Plugin de detecção de PPE (Personal Protective Equipment)."""

    name = "ppe_detection"
    version = "1.0.0"
    roi_type = "object_in_zone"

    async def initialize(self, config: dict) -> None:
        """Carrega modelo ppe.pt."""
        from ultralytics import YOLO

        model_path = config.get("model_path", "/models/ppe.pt")
        imgsz = config.get("imgsz", 640)
        self._model = YOLO(model_path)
        self._imgsz = imgsz
        self._conf = config.get("conf", 0.45)
        logger.info("PPEDetectionPlugin: modelo carregado de %s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame e detecta PPE violations."""
        detections = self.detect(frame, conf=self._conf)
        if not detections:
            return []

        results = []
        for det in detections:
            class_name = det["class_name"]
            confidence = det["confidence"]
            bbox = det["bbox"]

            # Verificar se é violação (sem EPI)
            is_violation = "No" in class_name or "NO" in class_name

            matched_roi = None
            if rois:
                for roi in rois:
                    if roi.ia_type == "ppe":
                        if self.point_in_polygon(self.centroid(bbox), roi.polygon_points):
                            matched_roi = roi
                            break

            if matched_roi or not rois:
                payload = {
                    "ppe_type": class_name,
                    "confidence": confidence,
                    "bbox": bbox,
                    "is_violation": is_violation,
                    "severity": "critical" if is_violation else "info",
                }

                result = AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    event_type="ppe_violation" if is_violation else "ppe_detected",
                    payload=payload,
                    occurred_at=datetime.utcnow(),
                    confidence=confidence,
                    roi_id=matched_roi.id if matched_roi else None,
                )
                results.append(result)

        return results
