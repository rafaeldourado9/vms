"""Plugin de reconhecimento de placas (LPR) — YOLOv8 + fast-plate-ocr."""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import numpy as np

from analytics.core.plugin_base import (
    AnalyticsPlugin,
    AnalyticsResult,
    FrameMetadata,
    ROIConfig,
)
from analytics.core.yolo_base import YOLOPlugin

logger = logging.getLogger(__name__)

# Regex para placas brasileiras (antiga AAA-1234 e Mercosul AAA1A23)
_PLATE_REGEX = re.compile(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$")


def normalize_plate(raw: str) -> str:
    """Normaliza texto de placa removendo caracteres especiais."""
    return re.sub(r"[^A-Z0-9]", "", raw.upper().strip())


class LPRPlugin(AnalyticsPlugin):
    """
    Reconhecimento de placas veiculares via YOLOv8 + fast-plate-ocr.

    Fluxo B: para câmeras sem módulo ANPR embarcado.

    Lógica:
    1. YOLOv8 detecta bbox da placa no frame
    2. Crop da região da placa
    3. fast-plate-ocr extrai texto
    4. Normaliza formato (AAA1234 ou AAA1A23)
    5. Cooldown Redis (mesmo plate + câmera < TTL = ignorar)
    6. Emite evento
    """

    name = "lpr"
    version = "1.0.0"
    roi_type = "lpr"

    def __init__(self) -> None:
        self._plate_detector: Any = None
        self._ocr: Any = None
        self._imgsz: int = 640
        self._cooldowns: dict[str, float] = {}

    async def initialize(self, config: dict) -> None:
        """Carrega modelo de detecção de placas e OCR."""
        from ultralytics import YOLO

        model_path = config.get("model_path", "yolov8n.pt")
        self._imgsz = config.get("imgsz", 640)
        self._plate_detector = YOLO(model_path)

        try:
            from fast_plate_ocr import ONNXPlateRecognizer

            self._ocr = ONNXPlateRecognizer("argentinian-plates-cnn-model")
        except Exception:
            logger.warning("fast-plate-ocr indisponível, LPR usará fallback sem OCR")
            self._ocr = None

        logger.info("LPR plugin inicializado: detector=%s", model_path)

    async def process_frame(
        self,
        frame: np.ndarray,
        metadata: FrameMetadata,
        rois: list[ROIConfig],
    ) -> list[AnalyticsResult]:
        """Processa frame para detecção e reconhecimento de placas."""
        results: list[AnalyticsResult] = []
        if self._plate_detector is None:
            return results

        # Detecta placas no frame inteiro
        preds = self._plate_detector.predict(
            frame,
            imgsz=self._imgsz,
            conf=0.3,
            verbose=False,
        )

        if not preds or preds[0].boxes is None or len(preds[0].boxes) == 0:
            return results

        h, w = frame.shape[:2]
        now = time.monotonic()

        for box in preds[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            plate_conf = float(box.conf[0])
            bbox_norm = [float(x1 / w), float(y1 / h), float(x2 / w), float(y2 / h)]
            cx, cy = (bbox_norm[0] + bbox_norm[2]) / 2, (bbox_norm[1] + bbox_norm[3]) / 2

            # Verifica em qual ROI o centroide da placa está
            matched_roi: ROIConfig | None = None
            for roi in rois:
                if YOLOPlugin.point_in_polygon((cx, cy), roi.polygon_points):
                    matched_roi = roi
                    break

            if not matched_roi:
                continue

            min_plate_conf = matched_roi.config.get("min_plate_confidence", 0.7)
            if plate_conf < min_plate_conf:
                continue

            # OCR no crop da placa
            plate_text = ""
            ocr_conf = 0.0

            ix1, iy1 = int(x1), int(y1)
            ix2, iy2 = int(x2), int(y2)
            crop = frame[iy1:iy2, ix1:ix2]

            if self._ocr is not None and crop.size > 0:
                try:
                    ocr_results = self._ocr.run(crop)
                    if ocr_results:
                        plate_text = str(ocr_results[0][0]) if isinstance(ocr_results[0], (list, tuple)) else str(ocr_results[0])
                        ocr_conf = float(ocr_results[0][1]) if isinstance(ocr_results[0], (list, tuple)) and len(ocr_results[0]) > 1 else 0.8
                except Exception:
                    logger.debug("OCR falhou para crop %dx%d", crop.shape[1], crop.shape[0])

            if not plate_text:
                continue

            plate_text = normalize_plate(plate_text)
            if not _PLATE_REGEX.match(plate_text):
                continue

            min_ocr_conf = matched_roi.config.get("min_ocr_confidence", 0.6)
            if ocr_conf < min_ocr_conf:
                continue

            # Cooldown
            dedup_ttl = matched_roi.config.get("dedup_ttl_seconds", 60)
            cooldown_key = f"{metadata.camera_id}:{plate_text}"
            last = self._cooldowns.get(cooldown_key, 0.0)
            if now - last < dedup_ttl:
                continue

            self._cooldowns[cooldown_key] = now
            results.append(
                AnalyticsResult(
                    plugin=self.name,
                    camera_id=metadata.camera_id,
                    tenant_id=metadata.tenant_id,
                    roi_id=matched_roi.id,
                    event_type="analytics.lpr.detected",
                    payload={
                        "roi_id": matched_roi.id,
                        "plate": plate_text,
                        "plate_confidence": round(plate_conf, 2),
                        "ocr_confidence": round(ocr_conf, 2),
                        "bbox": bbox_norm,
                    },
                    occurred_at=metadata.timestamp,
                )
            )

        return results

    async def shutdown(self) -> None:
        """Libera modelos."""
        self._plate_detector = None
        self._ocr = None
