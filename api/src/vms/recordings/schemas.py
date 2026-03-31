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
