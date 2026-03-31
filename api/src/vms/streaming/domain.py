"""Entidades de domínio de streaming."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class StreamSession:
    """Sessão de streaming ativa no MediaMTX."""

    id: str
    tenant_id: str
    camera_id: str
    mediamtx_path: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """Retorna True se a sessão ainda está ativa."""
        return self.ended_at is None

    def end(self) -> None:
        """Encerra a sessão de streaming."""
        self.ended_at = datetime.now(UTC)
