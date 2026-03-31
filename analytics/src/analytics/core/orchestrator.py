"""Orchestrator — captura frames, roteia para plugins, envia resultados."""
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

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordena captura de frames e roteamento para plugins.

    - Descobre e carrega plugins automaticamente de analytics.plugins.*
    - Para cada câmera, captura 1 frame/s via FrameSource
    - Busca ROIs da câmera periodicamente via VMSClient
    - Roteia frame + ROIs ao plugin correto (por ia_type ↔ roi_type)
    - Envia resultados ao VMS API
    """

    def __init__(self) -> None:
        self._plugins: dict[str, AnalyticsPlugin] = {}
        self._vms_client = VMSClient()
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []

    @property
    def plugins(self) -> dict[str, AnalyticsPlugin]:
        """Plugins carregados: {roi_type: plugin}."""
        return dict(self._plugins)

    async def load_plugins(self) -> None:
        """Escaneia analytics/plugins/*/plugin.py e carrega todos os plugins."""
        settings = get_settings()
        plugins_pkg = importlib.import_module("analytics.plugins")
        plugins_path = Path(plugins_pkg.__path__[0])

        for finder, name, ispkg in pkgutil.iter_modules([str(plugins_path)]):
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
                        self._plugins[plugin.roi_type] = plugin
                        logger.info(
                            "Plugin carregado: %s v%s (roi_type=%s)",
                            plugin.name,
                            plugin.version,
                            plugin.roi_type,
                        )
            except Exception:
                logger.exception("Erro ao carregar plugin %s", name)

    async def start(self, cameras: list[dict]) -> None:
        """
        Inicia captura para todas as câmeras.

        cameras: lista de dicts com keys camera_id, tenant_id, stream_url.
        """
        await self._vms_client.start()
        self._running = True

        settings = get_settings()
        for cam in cameras:
            task = asyncio.create_task(
                self._process_camera(
                    camera_id=cam["camera_id"],
                    tenant_id=cam["tenant_id"],
                    stream_url=cam["stream_url"],
                    fps=settings.analytics_fps,
                )
            )
            self._tasks.append(task)
        logger.info("Orchestrator iniciado para %d câmeras", len(cameras))

    async def stop(self) -> None:
        """Para captura de todas as câmeras e encerra plugins."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        for plugin in self._plugins.values():
            await plugin.shutdown()
        self._plugins.clear()

        await self._vms_client.close()
        logger.info("Orchestrator encerrado")

    async def _process_camera(
        self,
        camera_id: str,
        tenant_id: str,
        stream_url: str,
        fps: int,
    ) -> None:
        """Loop de processamento de uma câmera individual."""
        source = FrameSource(stream_url, fps=fps)
        if not source.open():
            logger.error("Não foi possível abrir câmera %s: %s", camera_id, stream_url)
            return

        roi_cache: list[ROIConfig] = []
        roi_refresh_counter = 0

        try:
            while self._running:
                frame = source.read()
                if frame is None:
                    await asyncio.sleep(0.05)
                    continue

                # Atualiza ROIs a cada 30 iterações (~30s com 1fps)
                roi_refresh_counter += 1
                if roi_refresh_counter >= 30 or not roi_cache:
                    roi_cache = await self._vms_client.get_camera_rois(camera_id)
                    roi_refresh_counter = 0

                if not roi_cache:
                    await asyncio.sleep(1.0 / fps)
                    continue

                metadata = FrameMetadata(
                    camera_id=camera_id,
                    tenant_id=tenant_id,
                    timestamp=__import__("datetime").datetime.utcnow(),
                    stream_url=stream_url,
                )

                for roi_type, plugin in self._plugins.items():
                    matching_rois = [r for r in roi_cache if r.ia_type == roi_type]
                    if not matching_rois:
                        continue

                    try:
                        results = await plugin.process_frame(frame, metadata, matching_rois)
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
        """Envia resultado de analytics para o VMS API."""
        payload = {
            "plugin": result.plugin,
            "camera_id": result.camera_id,
            "tenant_id": result.tenant_id,
            "roi_id": result.roi_id,
            "event_type": result.event_type,
            "payload": result.payload,
            "occurred_at": result.occurred_at.isoformat(),
        }
        await self._vms_client.ingest_result(payload)
