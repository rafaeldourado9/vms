"""Schemas Pydantic para VOD."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class VODStreamResponse(BaseModel):
    """Resposta de stream VOD."""

    id: str
    tenant_id: str
    camera_id: str
    started_at: datetime
    ended_at: datetime
    playlist_path: str = ""
    status: str
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateVODStreamRequest(BaseModel):
    """Request para criar stream VOD."""

    camera_id: str
    segment_ids: list[str] = Field(..., min_length=1, description="IDs dos segmentos de gravação")
    starts_at: datetime
    ends_at: datetime


class VODPlaylistURL(BaseModel):
    """Resposta com URL de playlist HLS."""

    playlist_url: str
    status: str
    stream_id: str
