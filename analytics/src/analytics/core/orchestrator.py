"""Orchestrator — descobre câmeras, captura frames e roteia para plugins."""
from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any

from analytics.core.config import get_settings
from analytics.core.frame_source import FrameSource
from analytics.core.plugin_base import (
    AnalyticsPlugin,
    AnalyticsResult,
    FrameMetadata,
    ROIConfig,
)
from analytics.core.vms_client import VMSClient
from analytics.core.zones import load_zones_config

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordena captura de frames e roteamento para plugins.

    Fluxo standalone:
    1. Descobre câmeras via GET /api/v1/plugins/cameras
    2. Obtém token RTSP via GET /api/v1/plugins/stream-token por câmera
    3. Captura frames de cada câmera a 1fps (configurável)
    4. Todos os plugins processam todos os frames
    5. Plugins usam zonas locais (zones.yaml ou env var) — sem dependência do VMS para config
    6. Resultados enviados via POST /api/v1/plugins/events
    """

    def __init__(self) -> None:
        self._plugins: list[AnalyticsPlugin] = []
        self._vms_client = VMSClient()
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def plugins(self) -> list[AnalyticsPlugin]:
        """Plugins carregados."""
        return list(self._plugins)

    async def load_plugins(self) -> None:
        """Escaneia analytics/plugins/*/plugin.py e carrega todos os plugins."""
        settings = get_settings()
        plugins_pkg = importlib.import_module("analytics.plugins")
        plugins_path = Path(plugins_pkg.__path__[0])

        for _finder, name, ispkg in pkgutil.iter_modules([str(plugins_path)]):
            if not ispkg:
                continue
            try:
                mod = importlib.import_module(f"analytics.plugins.{name}.plugin")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, AnalyticsPlugin)
                        and attr is not AnalyticsPlugin
                    ):
                        plugin = attr()
                        config: dict[str, Any] = {
                            "model_path": settings.yolo_model_path,
                            "imgsz": settings.yolo_imgsz,
                            "conf": settings.yolo_conf,
                        }
                        if hasattr(plugin, "name") and plugin.name == "lpr":
                            config["model_path"] = settings.lpr_model_path
                        await plugin.initialize(config)
                        self._plugins.append(plugin)
                        logger.info(
                            "Plugin carregado: %s v%s",
                            plugin.name,
                            plugin.version,
                        )
            except Exception:
                logger.exception("Erro ao carregar plugin %s", name)

    async def start(self) -> None:
        """Descobre câmeras via VMS API e inicia captura."""
        await self._vms_client.start()
        self._running = True

        cameras = await self._vms_client.list_cameras()
        if not cameras:
            logger.warning("Nenhuma câmera disponível via VMS API")

        settings = get_settings()
        zones_config = load_zones_config()

        for cam in cameras:
            if not cam.get("is_online", False):
                logger.debug("Câmera %s offline — ignorando", cam["id"])
                continue

            token_data = await self._vms_client.get_stream_token(cam["id"])
            if not token_data:
                logger.warning("Sem token de stream para câmera %s", cam["id"])
                continue

            task = asyncio.create_task(
                self._process_camera(
                    camera_id=cam["id"],
                    tenant_id=cam.get("tenant_id", ""),
                    rtsp_url=token_data["rtsp_url"],
                    fps=settings.analytics_fps,
                    zones=zones_config.get(cam["id"], []),
                )
            )
            self._tasks.append(task)

        logger.info(
            "Orchestrator iniciado: %d câmeras online, %d plugins ativos",
            len(self._tasks),
            len(self._plugins),
        )

    async def stop(self) -> None:
        """Para captura e encerra todos os plugins."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        for plugin in self._plugins:
            await plugin.shutdown()
        self._plugins.clear()

        await self._vms_client.close()
        logger.info("Orchestrator encerrado")

    async def _process_camera(
        self,
        camera_id: str,
        tenant_id: str,
        rtsp_url: str,
        fps: int,
        zones: list[ROIConfig],
    ) -> None:
        """Loop de processamento de uma câmera individual."""
        source = FrameSource(rtsp_url, fps=fps)
        if not source.open():
            logger.error("Não foi possível abrir câmera %s: %s", camera_id, rtsp_url)
            return

        try:
            while self._running:
                frame = source.read()
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                metadata = FrameMetadata(
                    camera_id=camera_id,
                    tenant_id=tenant_id,
                    timestamp=__import__("datetime").datetime.utcnow(),
                    stream_url=rtsp_url,
                )

                for plugin in self._plugins:
                    try:
                        results = await plugin.process_frame(frame, metadata, zones)
                        for result in results:
                            await self._send_result(result)
                    except Exception:
                        logger.exception(
                            "Erro no plugin %s para câmera %s",
                            plugin.name,
                            camera_id,
                        )
        finally:
            source.close()

    async def _send_result(self, result: AnalyticsResult) -> None:
        """Envia resultado do plugin ao VMS via contrato público."""
        payload: dict[str, Any] = {
            "plugin": result.plugin,
            **result.payload,
        }
        if result.roi_id:
            payload["roi_id"] = result.roi_id

        await self._vms_client.ingest_event(
            camera_id=result.camera_id,
            event_type=result.event_type,
            payload=payload,
            confidence=result.confidence,
            occurred_at=result.occurred_at.isoformat(),
        )
