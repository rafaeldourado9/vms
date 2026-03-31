"""Schemas Pydantic v2 para o bounded context de streaming."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PublishAuthRequest(BaseModel):
    """Payload de autenticação de publicação do MediaMTX."""

    action: str
    path: str
    query: str = ""


class ReadAuthRequest(BaseModel):
    """Payload de autenticação de leitura do MediaMTX."""

    action: str
    path: str
    query: str = ""


class PublishAuthResponse(BaseModel):
    """Resposta de autenticação de publicação."""

    ok: bool


class StreamSessionResponse(BaseModel):
    """Resposta com dados de uma sessão de streaming."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    camera_id: str
    mediamtx_path: str
    started_at: datetime
    ended_at: datetime | None
