"""Casos de uso do bounded context de gravações."""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import UTC, datetime, timedelta

from vms.recordings.domain import Clip, RecordingSegment
from vms.recordings.repository import ClipRepositoryPort, RecordingSegmentRepositoryPort

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")


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
        """
        resolved_tenant, resolved_camera = _resolve_ids(
            mediamtx_path, tenant_id, camera_id
        )
        started_at, ended_at, duration, size = _parse_file_metadata(file_path)

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
    """Extrai IDs do path MediaMTX se não fornecidos."""
    if tenant_id and camera_id:
        return tenant_id, camera_id
    match = _PATH_RE.match(mediamtx_path)
    if match:
        return match.group("tenant_id"), match.group("camera_id")
    return tenant_id, camera_id


def _parse_file_metadata(
    file_path: str,
) -> tuple[datetime, datetime, float, int]:
    """Extrai metadados básicos do arquivo de segmento."""
    now = datetime.now(UTC)
    size = 0
    duration = 60.0

    try:
        stat = os.stat(file_path)
        size = stat.st_size
    except OSError:
        pass

    started_at = now - timedelta(seconds=duration)
    return started_at, now, duration, size
