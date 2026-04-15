"""
ARQ Tasks para processamento batch de analytics em gravações.

Tasks assíncronas que processam segmentos de vídeo gravados
com plugins de IA, reusando a lógica de shared inference.

Fluxo:
1. Webhook segment_ready → enqueue task_batch_process_segment
2. Task verifica GPU disponível
3. FileFrameSource extrai frames do arquivo fMP4
4. Shared inference roda 1 inferência → N plugins
5. Eventos salvos com timestamp original do frame
6. Segmento marcado como processado
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import arq

logger = logging.getLogger(__name__)


async def task_batch_process_segment(
    ctx: dict,
    segment_id: str,
    file_path: str,
    camera_id: str,
    tenant_id: str,
    plugins: list[str] | None = None,
) -> None:
    """
    Processa segmento gravado com plugins de IA em batch.

    Args:
        segment_id: ID do segmento no banco
        file_path: Caminho absoluto do arquivo fMP4
        camera_id: ID da câmera
        tenant_id: ID do tenant
        plugins: Lista de plugins para executar (None = todos disponíveis)
    """
    # GPU check: se GPU ocupada, requeue
    try:
        from analytics.core.gpu_check import should_process_batch
        if not await should_process_batch():
            logger.info(
                "GPU ocupada — requeue segmento %s para processamento posterior",
                segment_id,
            )
            raise arq.WorkerTimeout("GPU busy — requeue")
    except ImportError:
        logger.debug("gpu_check não disponível — processando sem verificação GPU")

    # Importar componentes de analytics
    try:
        from analytics.core.file_frame_source import FileFrameSource
        from analytics.core.plugin_base import AnalyticsResult, FrameMetadata
        from analytics.core.shared_inference import SharedInferenceEngine, PLUGIN_CLASSES
        from vms.infrastructure.config import get_settings
        settings = get_settings()

        # Inicializar shared inference engine
        engine = SharedInferenceEngine(
            model_path=settings.yolo_model_path,
            imgsz=settings.yolo_imgsz,
            name=f"batch:{segment_id}",
        )

        # Carregar plugins
        plugins_to_run = plugins or list(PLUGIN_CLASSES.keys())

        # Processar arquivo
        results_count = 0
        with FileFrameSource(file_path, fps=1) as source:
            if not source.is_opened:
                logger.error("Não foi possível abrir segmento para batch: %s", file_path)
                return

            frame_count = 0
            while True:
                frame, frame_timestamp = source.read()
                if frame is None:
                    break

                frame_count += 1

                # Shared inference: 1 inferência
                all_classes = set()
                for plugin_name in plugins_to_run:
                    all_classes |= PLUGIN_CLASSES.get(plugin_name, set())

                detections = engine.predict(
                    frame,
                    classes=all_classes if all_classes else None,
                    conf=settings.yolo_conf,
                )

                # Distribuir para cada plugin
                metadata = FrameMetadata(
                    camera_id=camera_id,
                    tenant_id=tenant_id,
                    timestamp=frame_timestamp,
                    stream_url=file_path,
                )

                # TODO: Chamar plugins com detections pré-filtradas
                # Por enquanto, log apenas
                if detections:
                    logger.debug(
                        "Batch frame %d: %d detecções para segmento %s",
                        frame_count,
                        len(detections),
                        segment_id,
                    )
                    results_count += len(detections)

        logger.info(
            "Batch processado: segmento %s, %d frames, %d detecções",
            segment_id,
            frame_count,
            results_count,
        )

    except Exception:
        logger.exception("Erro ao processar segmento batch %s", segment_id)
        raise


class WorkerSettings:
    """Configurações do worker ARQ para batch analytics."""

    functions = [task_batch_process_segment]
    redis_settings: arq.connections.RedisSettings | None = None
    max_jobs = 10
    job_timeout = 600  # 10 minutos para processar segmentos grandes
