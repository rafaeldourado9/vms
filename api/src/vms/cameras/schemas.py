"""Schemas Pydantic v2 para o bounded context de câmeras e agents."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vms.cameras.domain import StreamProtocol


class CreateCameraRequest(BaseModel):
    """Dados para criação de uma nova câmera."""

    name: str = Field(..., min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=500)
    manufacturer: str = Field(default="generic")
    retention_days: int = Field(default=7, ge=1, le=90)
    stream_protocol: StreamProtocol = StreamProtocol.RTSP_PULL

    # rtsp_pull / onvif
    rtsp_url: str | None = Field(default=None, min_length=10, max_length=2000)
    agent_id: str | None = None

    # onvif
    onvif_url: str | None = Field(default=None, min_length=7, max_length=2000)
    onvif_username: str | None = Field(default=None, max_length=255)
    onvif_password: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _validate_protocol_fields(self) -> "CreateCameraRequest":
        if self.stream_protocol == StreamProtocol.RTSP_PULL:
            if not self.rtsp_url:
                raise ValueError("rtsp_url é obrigatório para stream_protocol=rtsp_pull")
        elif self.stream_protocol == StreamProtocol.ONVIF:
            if not self.onvif_url:
                raise ValueError("onvif_url é obrigatório para stream_protocol=onvif")
        # rtmp_push: nenhum campo adicional obrigatório — stream_key é gerado pelo serviço
        return self


class UpdateCameraRequest(BaseModel):
    """Dados para atualização parcial de uma câmera."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    location: str | None = None
    rtsp_url: str | None = Field(default=None, min_length=10, max_length=2000)
    onvif_url: str | None = Field(default=None, min_length=7, max_length=2000)
    onvif_username: str | None = Field(default=None, max_length=255)
    onvif_password: str | None = Field(default=None, max_length=500)
    manufacturer: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=90)
    agent_id: str | None = None
    ptz_supported: bool | None = None
    is_active: bool | None = None


class CameraResponse(BaseModel):
    """Resposta com dados completos de uma câmera."""

    model_config = {"from_attributes": True}

    id: str
    tenant_id: str
    name: str
    location: str | None
    stream_protocol: str
    rtsp_url: str | None
    rtmp_stream_key: str | None
    onvif_url: str | None
    onvif_username: str | None
    manufacturer: str
    retention_days: int
    ptz_supported: bool
    retention_days_pending: int | None
    retention_pending_from: datetime | None
    is_active: bool
    is_online: bool
    agent_id: str | None
    last_seen_at: datetime | None
    created_at: datetime


class StreamUrlsResponse(BaseModel):
    """URLs de streaming para um viewer."""

    hls_url: str
    webrtc_url: str
    rtsp_url: str | None
    token: str
    expires_at: datetime


class RtmpConfigResponse(BaseModel):
    """Configuração RTMP para câmeras push direto."""

    rtmp_url: str
    stream_key: str


class OnvifProbeRequest(BaseModel):
    """Dados para probe ONVIF de uma câmera."""

    onvif_url: str = Field(..., min_length=7, max_length=2000)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=500)


class OnvifProbeResponse(BaseModel):
    """Resultado do probe ONVIF."""

    reachable: bool
    manufacturer: str | None = None
    model: str | None = None
    rtsp_url: str | None = None
    snapshot_url: str | None = None
    error: str | None = None


class DiscoverOnvifRequest(BaseModel):
    """Parâmetros para WS-Discovery de câmeras ONVIF na rede."""

    subnet: str | None = Field(
        default=None,
        description="Subnet CIDR para busca (ex: 192.168.1.0/24). Sem este campo usa broadcast.",
    )
    timeout_seconds: int = Field(default=3, ge=1, le=10)


class DiscoveredCamera(BaseModel):
    """Câmera descoberta via WS-Discovery."""

    onvif_url: str
    manufacturer: str | None = None
    model: str | None = None
    ip: str


class DiscoverOnvifResponse(BaseModel):
    """Resultado da descoberta de câmeras ONVIF."""

    cameras: list[DiscoveredCamera]
    duration_ms: int


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
