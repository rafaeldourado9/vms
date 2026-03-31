"""Testes unitários do plugin intrusion_detection."""
from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.plugins.intrusion.plugin import IntrusionDetectionPlugin


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin() -> IntrusionDetectionPlugin:
    """Plugin de intrusão sem modelo YOLO carregado (detect mockado)."""
    return IntrusionDetectionPlugin()


@pytest.fixture
def metadata() -> FrameMetadata:
    """Metadados de frame para testes."""
    return FrameMetadata(
        camera_id="cam-001",
        tenant_id="tenant-001",
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        stream_url="rtsp://fake/stream",
    )


@pytest.fixture
def roi_intrusion() -> ROIConfig:
    """ROI de intrusão cobrindo quadrante superior-esquerdo."""
    return ROIConfig(
        id="roi-001",
        name="Zona Proibida",
        ia_type="intrusion",
        polygon_points=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
        config={"classes": [0], "min_confidence": 0.5, "cooldown_seconds": 30},
    )


@pytest.fixture
def frame() -> np.ndarray:
    """Frame sintético 640x480 RGB."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ── Testes ────────────────────────────────────────────────────────────────────

class TestIntrusionDetection:
    """Testes do plugin de detecção de intrusão."""

    @pytest.mark.asyncio
    async def test_detecta_pessoa_dentro_da_roi(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Deve emitir evento quando pessoa detectada dentro da ROI."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.1, 0.1, 0.3, 0.3]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(results) == 1
        assert results[0].event_type == "analytics.intrusion.detected"
        assert results[0].payload["detection_count"] == 1
        assert results[0].roi_id == "roi-001"

    @pytest.mark.asyncio
    async def test_nao_detecta_quando_fora_da_roi(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Não deve emitir evento quando detecção está fora do polígono."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.7, 0.7, 0.9, 0.9]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_nao_detecta_sem_deteccoes(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Não deve emitir evento quando YOLO não detecta nada."""
        with patch.object(plugin, "detect", return_value=[]):
            results = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_respeita_cooldown(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Não deve emitir segundo evento dentro do cooldown."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            r1 = await plugin.process_frame(frame, metadata, [roi_intrusion])
            r2 = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(r1) == 1
        assert len(r2) == 0  # cooldown ativo

    @pytest.mark.asyncio
    async def test_emite_apos_cooldown_expirar(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Deve emitir novamente após cooldown expirar."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            r1 = await plugin.process_frame(frame, metadata, [roi_intrusion])
            # Forçar expiração do cooldown
            plugin._cooldowns["roi-001"] = time.monotonic() - 31
            r2 = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_filtra_por_classe_configurada(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata,
    ):
        """Deve ignorar detecções de classes não configuradas."""
        roi = ROIConfig(
            id="roi-002",
            name="Zona Veículos",
            ia_type="intrusion",
            polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            config={"classes": [2], "min_confidence": 0.5, "cooldown_seconds": 0},
        )
        # Detecção é person (class_id=0), mas ROI quer car (class_id=2)
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi])

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_resultado_tem_campos_obrigatorios(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Resultado deve ter todos os campos obrigatórios do AnalyticsResult."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.1, 0.1, 0.3, 0.3]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_intrusion])

        r = results[0]
        assert isinstance(r, AnalyticsResult)
        assert r.plugin == "intrusion_detection"
        assert r.camera_id == "cam-001"
        assert r.tenant_id == "tenant-001"
        assert "detections" in r.payload
        assert "detection_count" in r.payload

    @pytest.mark.asyncio
    async def test_multiplas_deteccoes_na_roi(
        self, plugin: IntrusionDetectionPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_intrusion: ROIConfig,
    ):
        """Deve contar todas as detecções dentro da ROI."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"class_id": 0, "class_name": "person", "confidence": 0.75, "bbox": [0.3, 0.3, 0.4, 0.4]},
            {"class_id": 0, "class_name": "person", "confidence": 0.90, "bbox": [0.7, 0.7, 0.9, 0.9]},  # fora
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_intrusion])

        assert len(results) == 1
        assert results[0].payload["detection_count"] == 2
