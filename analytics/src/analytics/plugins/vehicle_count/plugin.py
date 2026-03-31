"""Plugin de contagem de veículos — YOLOv8n."""
from __future__ import annotations

import logging
import time

import numpy as np

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)

# Classes COCO para veículos
_VEHICLE_CLASSES = [2, 3, 5, 7]  # car, motorcycle, bus, truck


class VehicleCountPlugin(YOLOPlugin):
    """
    Conta veículos (car, motorcycle, bus, truck) dentro de uma ROI.

    Mesma lógica de people_count, filtrado por classes de veículos.
    """

    name = "vehicle_count"
    version = "1.0.0"
    roi_type = "vehicle_traffic"

    def __init__(self) -> None:
        super().__init__()
        self._last_emit: dict[str, float] = {}

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame para contagem de veículos em cada ROI."""
        results: list[AnalyticsResult] = []

        min_conf = min(
            (roi.config.get("min_confidence", 0.5) for roi in rois),
            default=0.5,
        )

        detections = self.detect(frame, conf=min_conf, classes=_VEHICLE_CLASSES)

        if not detections:
            return results

        now = time.monotonic()

        for roi in rois:
            interval = roi.config.get("interval_seconds", 60)
            last = self._last_emit.get(roi.id, 0.0)
            if now - last < interval:
                continue

            in_roi = self.filter_in_roi(detections, roi.polygon_points)
            count = len(in_roi)
            threshold = roi.config.get("emit_threshold", 0)

            if count > threshold:
                self._last_emit[roi.id] = now
                results.append(
                    AnalyticsResult(
                        plugin=self.name,
                        camera_id=metadata.camera_id,
                        tenant_id=metadata.tenant_id,
                        roi_id=roi.id,
                        event_type="analytics.vehicle.count",
                        payload={
                            "roi_id": roi.id,
                            "count": count,
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
