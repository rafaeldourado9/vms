"""Entidades de domínio de gravações e clipes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ClipStatus(StrEnum):
    """Estado de processamento de um clipe."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass
class RecordingSegment:
    """Segmento de gravação de 60s gerado pelo MediaMTX."""

    id: str
    tenant_id: str
    camera_id: str
    mediamtx_path: str
    file_path: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    size_bytes: int


@dataclass
class Clip:
    """Clipe de vídeo gerado a partir de segmentos de gravação."""

    id: str
    tenant_id: str
    camera_id: str
    starts_at: datetime
    ends_at: datetime
    status: ClipStatus = ClipStatus.PENDING
    file_path: str | None = None
    vms_event_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
