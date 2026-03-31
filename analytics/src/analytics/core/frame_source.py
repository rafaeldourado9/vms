"""Captura de frames RTSP via OpenCV."""
from __future__ import annotations

import logging
import time
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FrameSource:
    """
    Leitor de frames RTSP com controle de FPS.

    Abre stream RTSP via OpenCV e expõe frames a um framerate controlado.
    """

    def __init__(self, stream_url: str, fps: int = 1) -> None:
        self._url = stream_url
        self._fps = fps
        self._cap: Any = None
        self._last_read: float = 0.0

    def open(self) -> bool:
        """Abre conexão RTSP. Retorna True se sucesso."""
        self._cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            logger.error("Falha ao abrir stream: %s", self._url)
            return False
        logger.info("Stream aberto: %s", self._url)
        return True

    def read(self) -> np.ndarray | None:
        """
        Lê próximo frame respeitando o FPS configurado.

        Retorna None se não há frame disponível ou se não passou tempo suficiente.
        """
        if self._cap is None or not self._cap.isOpened():
            return None

        now = time.monotonic()
        interval = 1.0 / self._fps
        if now - self._last_read < interval:
            # Descarta frames para manter o FPS correto
            self._cap.grab()
            return None

        ret, frame = self._cap.read()
        if not ret:
            logger.warning("Falha ao ler frame de %s", self._url)
            return None

        self._last_read = now
        return frame

    def close(self) -> None:
        """Fecha a conexão com o stream."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Stream fechado: %s", self._url)

    @property
    def is_open(self) -> bool:
        """Verifica se o stream está aberto."""
        return self._cap is not None and self._cap.isOpened()
