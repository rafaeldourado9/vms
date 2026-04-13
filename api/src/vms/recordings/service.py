"""Casos de uso do bounded context de gravações."""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

from vms.recordings.domain import Clip, RecordingSegment
from vms.recordings.repository import ClipRepositoryPort, RecordingSegmentRepositoryPort
from vms.shared.value_objects import Sha256Hash

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")
_LIVE_RE = re.compile(r"live/(?P<stream_key>[^/]+?)(?:\.stream)?$")
_DATETIME_PATH_RE = re.compile(
    r"/(\d{4})/(\d{2})/(\d{2})/(\d{2})-(\d{2})-(\d{2})\.mp4$"
)


class RecordingService:
    """Casos de uso de indexação e gerenciamento de gravações."""

    def __init__(
        self,
        segment_repo: RecordingSegmentRepositoryPort,
        clip_repo: ClipRepositoryPort,
    ) -> None:
        self._segments = segment_repo
        self._clips = clip_repo

    async def index_segment(
        self,
        tenant_id: str,
        camera_id: str,
        file_path: str,
        mediamtx_path: str,
    ) -> RecordingSegment:
        """
        Indexa segmento de gravação.

        Extrai tenant_id/camera_id do mediamtx_path se não fornecidos explicitamente.
        Calcula SHA-256 do arquivo para cadeia de custódia.
        """
        resolved_tenant, resolved_camera = _resolve_ids(
            mediamtx_path, tenant_id, camera_id
        )
        started_at, ended_at, duration, size = _parse_file_metadata(file_path)

        # Calcular SHA-256 se arquivo existe
        sha256_hash = None
        try:
            if os.path.exists(file_path):
                sha256_hash = Sha256Hash.from_file(file_path)
                logger.debug("SHA-256 calculado para segmento: %s", file_path)
        except Exception:
            logger.warning("Falha ao calcular SHA-256 para %s (não crítico)", file_path, exc_info=True)

        segment = RecordingSegment(
            id=str(uuid.uuid4()),
            tenant_id=resolved_tenant,
            camera_id=resolved_camera,
            mediamtx_path=mediamtx_path,
            file_path=file_path,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration,
            size_bytes=size,
            sha256_hash=sha256_hash,
        )
        return await self._segments.create(segment)

    async def cleanup_expired_segments(
        self, tenant_id: str, camera_id: str, retention_days: int
    ) -> int:
        """Remove segmentos expirados. Retorna quantidade de registros removidos."""
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        count = await self._segments.delete_older_than(tenant_id, camera_id, cutoff)
        logger.info(
            "Limpeza: %d segmentos removidos — tenant=%s camera=%s retenção=%dd",
            count,
            tenant_id,
            camera_id,
            retention_days,
        )
        return count

    async def create_clip(
        self,
        tenant_id: str,
        camera_id: str,
        starts_at: datetime,
        ends_at: datetime,
        vms_event_id: str | None = None,
    ) -> Clip:
        """Cria solicitação de clipe. O processamento ocorre via tarefa background."""
        clip = Clip(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            starts_at=starts_at,
            ends_at=ends_at,
            vms_event_id=vms_event_id,
        )
        return await self._clips.create(clip)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_ids(
    mediamtx_path: str,
    tenant_id: str,
    camera_id: str,
) -> tuple[str, str]:
    """
    Extrai IDs do path MediaMTX se não fornecidos.

    Suporta dois formatos:
    - tenant-{tid}/cam-{cid}  → extrai tenant_id e camera_id diretamente
    - live/{stream_key}       → IDs devem ser fornecidos explicitamente (pelo webhook)
    """
    if tenant_id and camera_id:
        return tenant_id, camera_id
    match = _PATH_RE.match(mediamtx_path)
    if match:
        return match.group("tenant_id"), match.group("camera_id")
    return tenant_id, camera_id


def _parse_file_metadata(
    file_path: str,
) -> tuple[datetime, datetime, float, int]:
    """Extrai metadados básicos do arquivo de segmento.

    Parseia o timestamp real do path MediaMTX: /YYYY/MM/DD/HH-MM-SS.mp4
    Corrige double extension (.mp4.mp4) se presente.
    Garante path absoluto com leading slash.
    """
    now = datetime.now(UTC)
    size = 0
    duration = 60.0

    # Corrige double extension: MediaMTX às vezes adiciona .mp4 extra
    if file_path.endswith(".mp4.mp4"):
        file_path = file_path[:-4]

    # Garante path absoluto
    if not file_path.startswith("/"):
        file_path = f"/{file_path}"

    try:
        stat = os.stat(file_path)
        size = stat.st_size
    except OSError:
        pass

    # Parseia timestamp do path: /recordings/tenant-X/cam-Y/YYYY/MM/DD/HH-MM-SS.mp4
    m = _DATETIME_PATH_RE.search(file_path)
    if m:
        y, mo, d, h, mi, s = map(int, m.groups())
        started_at = datetime(y, mo, d, h, mi, s, tzinfo=UTC)
        ended_at = started_at + timedelta(seconds=duration)
    else:
        started_at = now - timedelta(seconds=duration)
        ended_at = now

    return started_at, ended_at, duration, size
