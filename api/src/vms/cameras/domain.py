"""Entidades de domínio de câmeras e agents."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class CameraManufacturer(StrEnum):
    """Fabricantes de câmera suportados."""

    HIKVISION = "hikvision"
    INTELBRAS = "intelbras"
    DAHUA = "dahua"
    GENERIC = "generic"


class AgentStatus(StrEnum):
    """Estado do agent local."""

    PENDING = "pending"
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass
class Agent:
    """Agent local que captura streams RTSP e envia via RTMP."""

    id: str
    tenant_id: str
    name: str
    status: AgentStatus = AgentStatus.PENDING
    last_heartbeat_at: datetime | None = None
    version: str | None = None
    streams_running: int = 0
    streams_failed: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def mark_online(
        self,
        version: str,
        streams_running: int,
        streams_failed: int,
    ) -> None:
        """Marca agent como online com dados do heartbeat."""
        from datetime import UTC

        self.status = AgentStatus.ONLINE
        self.last_heartbeat_at = datetime.now(UTC)
        self.version = version
        self.streams_running = streams_running
        self.streams_failed = streams_failed

    def mark_offline(self) -> None:
        """Marca agent como offline."""
        self.status = AgentStatus.OFFLINE


@dataclass
class Camera:
    """Câmera de segurança gerenciada pelo VMS."""

    id: str
    tenant_id: str
    name: str
    rtsp_url: str
    manufacturer: CameraManufacturer
    location: str | None = None
    agent_id: str | None = None
    retention_days: int = 7
    is_active: bool = True
    is_online: bool = False
    last_seen_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def mediamtx_path(self) -> str:
        """Retorna o path do stream no MediaMTX."""
        return f"tenant-{self.tenant_id}/cam-{self.id}"

    @property
    def rtmp_push_url(self) -> str:
        """URL RTMP para o agent fazer push (preenchida pelo service com config)."""
        return ""  # preenchida pelo service

    def mark_online(self) -> None:
        """Marca câmera como online e atualiza last_seen_at."""
        from datetime import UTC

        self.is_online = True
        self.last_seen_at = datetime.now(UTC)

    def mark_offline(self) -> None:
        """Marca câmera como offline."""
        self.is_online = False


@dataclass
class CameraConfig:
    """Configuração de uma câmera para o agent."""

    id: str
    name: str
    rtsp_url: str
    rtmp_push_url: str
    enabled: bool
