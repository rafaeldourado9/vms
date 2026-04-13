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
from analytics.core.shared_inference import (
    PLUGIN_CLASSES,
    SharedInferenceEngine,
)
from analytics.core.vms_client import VMSClient
from analytics.core.zones import load_zones_config  # fallback local

logger = logging.getLogger(__name__)

# Modelos que podem ser compartilhados entre plugins
SHARED_MODELS = {
    "object.pt": {"intrusion", "people_count", "vehicle_count", "lpr", "biker_detection"},
}


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
        self._shared_engines: dict[str, SharedInferenceEngine] = {}
        self._plugin_uses_shared: dict[str, str] = {}  # plugin_name -> engine_name
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
                        and not getattr(attr, "__abstractmethods__", set())
                    ):
                        plugin = attr()
                        config: dict[str, Any] = {
                            "model_path": settings.yolo_model_path,
                            "imgsz": settings.yolo_imgsz,
                            "conf": settings.yolo_conf,
                        }

                        # Configurar modelo específico por plugin
                        if plugin.name == "lpr":
                            config["model_path"] = settings.lpr_model_path
                        elif plugin.name == "fire_smoke":
                            config["model_path"] = settings.fire_smoke_model_path
                        elif plugin.name == "ppe_detection":
                            config["model_path"] = settings.ppe_model_path
                        elif plugin.name == "biker_detection":
                            config["model_path"] = settings.biker_model_path
                        elif plugin.name == "horse_cart":
                            config["model_path"] = settings.horse_cart_model_path
                        await plugin.initialize(config)
                        self._plugins.append(plugin)
                        logger.info(
                            "Plugin carregado: %s v%s",
                            plugin.name,
                            plugin.version,
                        )
            except Exception:
                logger.exception("Erro ao carregar plugin %s", name)

        # Criar shared inference engines para plugins que compartilham modelo
        await self._build_shared_engines(settings)

    async def _build_shared_engines(self, settings: Any) -> None:
        """
        Cria SharedInferenceEngine para modelos compartilhados.

        Plugins que usam o mesmo modelo (ex: object.pt) compartilham
        uma única engine. A união de todas as classes necessárias
        é computada para maximizar eficiência.
        """
        # Determinar quais plugins podem usar shared inference
        model_path = settings.yolo_model_path
        model_key = model_path.split("/")[-1]  # "object.pt"

        if model_key in SHARED_MODELS:
            plugin_names = SHARED_MODELS[model_key]
            # Filtrar apenas plugins que foram carregados
            loaded_plugin_names = {p.name for p in self._plugins}
            active_plugin_names = plugin_names & loaded_plugin_names

            if active_plugin_names:
                # Unir todas as classes necessárias
                all_classes: set[int] = set()
                for pname in active_plugin_names:
                    all_classes |= PLUGIN_CLASSES.get(pname, set())

                engine = SharedInferenceEngine(
                    model_path=model_path,
                    imgsz=settings.yolo_imgsz,
                    name=f"shared:{model_key}",
                )
                engine_key = f"shared:{model_key}"
                self._shared_engines[engine_key] = engine
                logger.info(
                    "Shared engine criada para %s: %d classes (%s) para plugins: %s",
                    model_key,
                    len(all_classes),
                    sorted(all_classes),
                    sorted(active_plugin_names),
                )

                # Registrar quais plugins usam esta engine
                for pname in active_plugin_names:
                    self._plugin_uses_shared[pname] = engine_key

                # Armazenar classes unidas na engine para acesso rápido
                engine._all_classes = all_classes  # type: ignore[attr-defined]

    async def start(self) -> None:
        """Descobre câmeras via VMS API e inicia captura."""
        await self._vms_client.start()
        self._running = True

        cameras = await self._vms_client.list_cameras()
        if not cameras:
            logger.warning("Nenhuma câmera disponível via VMS API")

        settings = get_settings()

        # Tenta buscar ROIs da API; fallback para zones.yaml local
        api_rois = await self._vms_client.list_rois()
        if api_rois:
            zones_config: dict[str, list[ROIConfig]] = {}
            for roi in api_rois:
                cam_id = roi["camera_id"]
                zones_config.setdefault(cam_id, []).append(
                    ROIConfig(
                        id=roi["id"],
                        name=roi["name"],
                        ia_type=roi["plugin_id"],
                        polygon_points=roi["polygon_points"],
                        config=roi.get("config", {}),
                    )
                )
            logger.info("ROIs carregadas da API: %d zonas em %d câmeras", len(api_rois), len(zones_config))
        else:
            zones_config = load_zones_config()
            logger.info("ROIs locais (zones.yaml): %d câmeras configuradas", len(zones_config))

        for cam in cameras:
            if not cam.get("is_online", False):
                logger.debug("Câmera %s offline — ignorando", cam["id"])
                continue

            # Tenta construir RTSP URL direto do MediaMTX (sem token JWT)
            rtsp_url = self._build_mediamtx_rtsp(cam)
            if not rtsp_url:
                # Fallback: usa token da VMS API
                token_data = await self._vms_client.get_stream_token(cam["id"])
                if not token_data:
                    logger.warning("Sem token de stream para câmera %s", cam["id"])
                    continue
                rtsp_url = token_data["rtsp_url"]

            task = asyncio.create_task(
                self._process_camera(
                    camera_id=cam["id"],
                    tenant_id=cam.get("tenant_id", ""),
                    rtsp_url=rtsp_url,
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

    def _build_mediamtx_rtsp(self, camera: dict) -> str | None:
        """
        Constrói URL RTSP direto do MediaMTX para câmera online.

        Usa mediamtx_path da câmera (ex: tenant-xxx/cam-yyy) para montar:
        rtsp://mediamtx:8554/tenant-xxx/cam-yyy

        Retorna None se não há mediamtx_path ou mediamtx_host configurado.
        """
        mediamtx_path = camera.get("mediamtx_path")
        if not mediamtx_path:
            logger.debug(
                "Câmera %s sem mediamtx_path — impossível construir RTSP local",
                camera.get("id"),
            )
            return None

        settings = get_settings()
        host = settings.mediamtx_host
        rtsp_port = getattr(settings, "mediamtx_rtsp_port", 8554)

        # URL RTSP simples (sem token JWT)
        rtsp_url = f"rtsp://{host}:{rtsp_port}/{mediamtx_path}"
        logger.info(
            "RTSP local construído para câmera %s: %s",
            camera.get("id"),
            rtsp_url,
        )
        return rtsp_url

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

        # Separar plugins que usam shared inference vs standalone
        shared_plugins: list[AnalyticsPlugin] = []
        standalone_plugins: list[AnalyticsPlugin] = []
        for plugin in self._plugins:
            if plugin.name in self._plugin_uses_shared:
                shared_plugins.append(plugin)
            else:
                standalone_plugins.append(plugin)

        # Buscar plugins ativos para esta câmera (filtro por PluginInstallation)
        active_plugin_names = await self._vms_client.get_active_plugins_for_camera(
            camera_id
        )
        # Se API retornar vazio (endpoint não existe ou falha), usar todos os plugins
        use_plugin_filter = len(active_plugin_names) > 0

        def is_plugin_active(plugin_name: str) -> bool:
            if not use_plugin_filter:
                return True
            return plugin_name in active_plugin_names

        # Filtrar plugins ativos
        shared_plugins = [p for p in shared_plugins if is_plugin_active(p.name)]
        standalone_plugins = [p for p in standalone_plugins if is_plugin_active(p.name)]

        if not shared_plugins and not standalone_plugins:
            logger.debug(
                "Nenhum plugin ativo para câmera %s — pulando processamento",
                camera_id,
            )
            source.close()
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

                # 1. Shared inference: 1 inferência → múltiplos plugins
                if shared_plugins and self._shared_engines:
                    # Pegar a primeira engine compartilhada (assumimos 1 modelo compartilhado)
                    engine_key = next(iter(self._shared_engines))
                    engine = self._shared_engines[engine_key]
                    all_classes = getattr(engine, "_all_classes", set())

                    # Executar inferência UNA
                    shared_detections = engine.predict(
                        frame,
                        classes=all_classes,
                        conf=0.30,
                    )

                    # Distribuir para cada plugin (cada um filtra suas classes)
                    for plugin in shared_plugins:
                        try:
                            plugin_classes = PLUGIN_CLASSES.get(plugin.name, set())
                            plugin_detections = engine.filter_by_class(
                                shared_detections,
                                plugin_classes,
                            )
                            results = await plugin.process_shared_frame(
                                plugin_detections,
                                frame,
                                metadata,
                                zones,
                            )
                            for result in results:
                                await self._send_result(result)
                        except Exception:
                            logger.exception(
                                "Erro no plugin shared %s para câmera %s",
                                plugin.name,
                                camera_id,
                            )

                # 2. Standalone inference: plugins com modelo próprio
                for plugin in standalone_plugins:
                    try:
                        results = await plugin.process_frame(frame, metadata, zones)
                        for result in results:
                            await self._send_result(result)
                    except Exception:
                        logger.exception(
                            "Erro no plugin standalone %s para câmera %s",
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
