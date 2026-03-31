"""Testes unitários do plugin people_count."""
from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import patch

import numpy as np
import pytest

from analytics.core.plugin_base import AnalyticsResult, FrameMetadata, ROIConfig
from analytics.plugins.people_count.plugin import PeopleCountPlugin


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin() -> PeopleCountPlugin:
    """Plugin de contagem de pessoas (detect mockado)."""
    return PeopleCountPlugin()


@pytest.fixture
def metadata() -> FrameMetadata:
    return FrameMetadata(
        camera_id="cam-001",
        tenant_id="tenant-001",
        timestamp=datetime(2026, 3, 30, 12, 0, 0),
        stream_url="rtsp://fake/stream",
    )


@pytest.fixture
def roi_people() -> ROIConfig:
    """ROI cobrindo frame inteiro."""
    return ROIConfig(
        id="roi-ppl-001",
        name="Entrada Principal",
        ia_type="human_traffic",
        polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        config={"emit_threshold": 0, "interval_seconds": 60, "min_confidence": 0.5},
    )


@pytest.fixture
def frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


# ── Testes ────────────────────────────────────────────────────────────────────

class TestPeopleCount:
    """Testes do plugin de contagem de pessoas."""

    @pytest.mark.asyncio
    async def test_conta_pessoas_dentro_da_roi(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_people: ROIConfig,
    ):
        """Deve emitir contagem quando há pessoas na ROI."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.1, 0.1, 0.3, 0.3]},
            {"class_id": 0, "class_name": "person", "confidence": 0.75, "bbox": [0.5, 0.5, 0.7, 0.7]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_people])

        assert len(results) == 1
        assert results[0].event_type == "analytics.people.count"
        assert results[0].payload["count"] == 2

    @pytest.mark.asyncio
    async def test_nao_emite_sem_deteccoes(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_people: ROIConfig,
    ):
        """Não deve emitir quando ninguém detectado."""
        with patch.object(plugin, "detect", return_value=[]):
            results = await plugin.process_frame(frame, metadata, [roi_people])

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_respeita_threshold(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata,
    ):
        """Não deve emitir se contagem <= threshold."""
        roi = ROIConfig(
            id="roi-t",
            name="Threshold 5",
            ia_type="human_traffic",
            polygon_points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            config={"emit_threshold": 5, "interval_seconds": 0},
        )
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
            {"class_id": 0, "class_name": "person", "confidence": 0.75, "bbox": [0.5, 0.5, 0.7, 0.7]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi])

        assert len(results) == 0  # count=2 <= threshold=5

    @pytest.mark.asyncio
    async def test_respeita_intervalo(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_people: ROIConfig,
    ):
        """Não deve emitir segundo evento dentro do intervalo mínimo."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            r1 = await plugin.process_frame(frame, metadata, [roi_people])
            r2 = await plugin.process_frame(frame, metadata, [roi_people])

        assert len(r1) == 1
        assert len(r2) == 0

    @pytest.mark.asyncio
    async def test_emite_apos_intervalo(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_people: ROIConfig,
    ):
        """Deve emitir novamente após intervalo expirar."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            r1 = await plugin.process_frame(frame, metadata, [roi_people])
            plugin._last_emit["roi-ppl-001"] = time.monotonic() - 61
            r2 = await plugin.process_frame(frame, metadata, [roi_people])

        assert len(r1) == 1
        assert len(r2) == 1

    @pytest.mark.asyncio
    async def test_resultado_tem_campos_obrigatorios(
        self, plugin: PeopleCountPlugin, frame: np.ndarray,
        metadata: FrameMetadata, roi_people: ROIConfig,
    ):
        """Resultado deve ter campos obrigatórios."""
        detections = [
            {"class_id": 0, "class_name": "person", "confidence": 0.87, "bbox": [0.2, 0.2, 0.4, 0.4]},
        ]
        with patch.object(plugin, "detect", return_value=detections):
            results = await plugin.process_frame(frame, metadata, [roi_people])

        r = results[0]
        assert isinstance(r, AnalyticsResult)
        assert r.plugin == "people_count"
        assert "count" in r.payload
        assert "detections" in r.payload
