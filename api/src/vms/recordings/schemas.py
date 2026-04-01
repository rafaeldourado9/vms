"""Schemas Pydantic v2 para o bounded context de gravações."""
from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, Field


class RecordingSegmentResponse(BaseModel):
    """Resposta com dados de um segmento de gravação."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    camera_id: str
    mediamtx_path: str
    file_path: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: float
    size_bytes: int


class ClipResponse(BaseModel):
    """Resposta com dados de um clipe."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    camera_id: str
    starts_at: datetime
    ends_at: datetime
    status: str
    file_path: str | None
    vms_event_id: str | None
    created_at: datetime


class CreateClipRequest(BaseModel):
    """Dados para criação de um clipe."""

    camera_id: str
    starts_at: datetime
    ends_at: datetime
    vms_event_id: str | None = None

    @property
    def duration_seconds(self) -> float:
        """Duração do clipe em segundos."""
        return (self.ends_at - self.starts_at).total_seconds()


class SegmentListResponse(BaseModel):
    """Resposta paginada de lista de segmentos."""

    items: list[RecordingSegmentResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[RecordingSegmentResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "SegmentListResponse":
        """Constrói resposta calculando total de páginas."""
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class ClipListResponse(BaseModel):
    """Resposta paginada de lista de clipes."""

    items: list[ClipResponse]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[ClipResponse],
        total: int,
        page: int,
        page_size: int,
    ) -> "ClipListResponse":
        """Constrói resposta calculando total de páginas."""
        pages = math.ceil(total / page_size) if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)


class TimelineHourResponse(BaseModel):
    """Agrupamento de segmentos por hora para UI de playback."""

    hour: datetime
    segments: list[RecordingSegmentResponse]
    coverage_pct: float
    minutes_recorded: int = Field(default=0, description="Minutos gravados na hora (0-60)")

    @classmethod
    def from_segments(
        cls, hour: datetime, segments: list[RecordingSegmentResponse]
    ) -> "TimelineHourResponse":
        """Constrói resposta calculando coverage e minutos a partir dos segmentos."""
        total_duration = sum(s.duration_seconds for s in segments)
        coverage_pct = min(total_duration / 3600.0, 1.0)
        return cls(
            hour=hour,
            segments=segments,
            coverage_pct=round(coverage_pct, 4),
            minutes_recorded=min(int(total_duration / 60), 60),
        )


class VodResponse(BaseModel):
    """URL HLS VOD para playback de gravações via MediaMTX."""

    hls_url: str = Field(..., description="URL HLS VOD — alimentar diretamente no HLS.js")
    token: str = Field(..., description="ViewerToken JWT incluído na URL")
    expires_at: datetime = Field(..., description="Expiração do ViewerToken")
    segments_count: int = Field(..., description="Número de segmentos encontrados no período")
    has_gaps: bool = Field(..., description="True se houver gaps de gravação no período")
