"""Schemas Pydantic v2 para o bounded context de câmeras e agents."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class CreateCameraRequest(BaseModel):
    """Dados para criação de uma nova câmera."""

    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=500)
    rtsp_url: str = Field(..., min_length=10, max_length=2000)
    manufacturer: str = Field(default="generic")
    retention_days: int = Field(default=7, ge=1, le=90)
    agent_id: str | None = None


class UpdateCameraRequest(BaseModel):
    """Dados para atualização parcial de uma câmera."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = None
    rtsp_url: str | None = Field(default=None, min_length=10, max_length=2000)
    manufacturer: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=90)
    agent_id: str | None = None
    is_active: bool | None = None


class CameraResponse(BaseModel):
    """Resposta com dados completos de uma câmera."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    name: str
    location: str | None
    rtsp_url: str
    manufacturer: str
    retention_days: int
    is_active: bool
    is_online: bool
    agent_id: str | None
    last_seen_at: datetime | None
    created_at: datetime


class CreateAgentRequest(BaseModel):
    """Dados para criação de um novo agent."""

    name: str = Field(..., min_length=1, max_length=255)


class AgentResponse(BaseModel):
    """Resposta com dados de um agent."""

    model_config = {"from_attributes": True}

    id: str
    name: str
    status: str
    last_heartbeat_at: datetime | None
    version: str | None
    streams_running: int
    streams_failed: int
    created_at: datetime


class CreateAgentResponse(AgentResponse):
    """Resposta de criação de agent — inclui a API key em texto plano (única vez)."""

    api_key: str = Field(..., description="API key em texto plano. Guarde — não será exibida novamente.")


class CameraConfigItem(BaseModel):
    """Item de configuração de câmera para o agent."""

    id: str
    name: str
    rtsp_url: str
    rtmp_push_url: str
    enabled: bool


class AgentConfigResponse(BaseModel):
    """Configuração completa do agent — retornada no endpoint /agents/me/config."""

    agent_id: str
    cameras: list[CameraConfigItem]


class HeartbeatRequest(BaseModel):
    """Dados de heartbeat enviados pelo agent."""

    version: str = Field(..., min_length=1, max_length=50)
    streams_running: int = Field(..., ge=0)
    streams_failed: int = Field(..., ge=0)
    uptime_seconds: int = Field(..., ge=0)
