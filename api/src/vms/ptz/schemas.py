"""Schemas Pydantic v2 para o bounded context PTZ."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PtzMoveRequest(BaseModel):
    """Parâmetros de movimento contínuo PTZ."""

    pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Pan: -1.0 esq → 1.0 dir")
    tilt: float = Field(default=0.0, ge=-1.0, le=1.0, description="Tilt: -1.0 baixo → 1.0 cima")
    zoom: float = Field(default=0.0, ge=0.0, le=1.0, description="Zoom: 0.0 afastado → 1.0 próximo")
    timeout_seconds: int = Field(default=5, ge=1, le=60, description="Duração máxima do movimento")


class PtzPresetResponse(BaseModel):
    """Dados de um preset PTZ."""

    token: str
    name: str


class PtzPresetsResponse(BaseModel):
    """Lista de presets PTZ da câmera."""

    presets: list[PtzPresetResponse]


class SavePresetRequest(BaseModel):
    """Dados para salvar/sobrescrever um preset PTZ."""

    name: str = Field(..., min_length=1, max_length=64, description="Nome do preset")


class PtzActionResponse(BaseModel):
    """Confirmação de execução de comando PTZ."""

    ok: bool = True
    message: str = ""
