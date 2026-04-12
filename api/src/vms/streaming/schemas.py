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


class AnalyticsAuthRequest(BaseModel):
    """
    Payload de autenticação para analytics service.
    
    MediaMTX chama este endpoint quando o analytics tenta ler um stream.
    Apenas verifica se o path existe e a câmera está online — sem validar token.
    """

    action: str
    path: str
    query: str = ""
    # Headers adicionais que identificam o cliente
    x_analytics_service: str = ""


class StreamSessionResponse(BaseModel):
    """Resposta com dados de uma sessão de streaming."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    camera_id: str
    mediamtx_path: str
    started_at: datetime
    ended_at: datetime | None
