"""Schemas Pydantic para o bounded context de configuração de analytics."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

_VALID_IA_TYPES = {"intrusion", "human_traffic", "vehicle_traffic", "lpr"}


class CreateROIRequest(BaseModel):
    """Payload para criação de Região de Interesse."""

    camera_id: str = Field(..., description="ID da câmera")
    name: str = Field(..., min_length=1, max_length=255, description="Nome da região")
    ia_type: str = Field(
        ...,
        description="Tipo de análise: intrusion | human_traffic | vehicle_traffic | lpr",
    )
    polygon_points: list[list[float]] = Field(
        ...,
        min_length=3,
        description="Vértices do polígono normalizados [0.0, 1.0]",
    )
    config: dict = Field(default_factory=dict, description="Configuração extra por tipo de análise")
    is_active: bool = Field(default=True)

    @field_validator("ia_type")
    @classmethod
    def validar_ia_type(cls, v: str) -> str:
        """Valida que ia_type é um dos valores suportados."""
        if v not in _VALID_IA_TYPES:
            raise ValueError(f"ia_type deve ser um de: {_VALID_IA_TYPES}")
        return v

    @field_validator("polygon_points")
    @classmethod
    def validar_poligono(cls, v: list[list[float]]) -> list[list[float]]:
        """Valida que cada ponto tem exatamente 2 coordenadas no intervalo [0, 1]."""
        for point in v:
            if len(point) != 2:  # noqa: PLR2004
                raise ValueError("Cada ponto deve ter exatamente 2 coordenadas [x, y]")
            if not all(0.0 <= c <= 1.0 for c in point):
                raise ValueError("Coordenadas devem ser normalizadas entre 0.0 e 1.0")
        return v


class UpdateROIRequest(BaseModel):
    """Payload parcial para atualização de ROI."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    ia_type: str | None = Field(default=None)
    polygon_points: list[list[float]] | None = Field(default=None, min_length=3)
    config: dict | None = Field(default=None)
    is_active: bool | None = Field(default=None)

    @field_validator("ia_type")
    @classmethod
    def validar_ia_type(cls, v: str | None) -> str | None:
        """Valida ia_type se fornecido."""
        if v is not None and v not in _VALID_IA_TYPES:
            raise ValueError(f"ia_type deve ser um de: {_VALID_IA_TYPES}")
        return v


class ROIResponse(BaseModel):
    """Resposta com dados completos de uma ROI."""

    id: str
    tenant_id: str
    camera_id: str
    name: str
    ia_type: str
    polygon_points: list[list[float]]
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ROIForAnalytics(BaseModel):
    """Schema retornado para o analytics_service via endpoint interno."""

    id: str
    camera_id: str
    name: str
    ia_type: str
    polygon_points: list[list[float]]
    config: dict
