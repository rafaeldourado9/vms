"""Entidades de domínio para configuração de analytics (ROIs)."""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RegionOfInterest:
    """Região de interesse configurada para análise de IA."""

    id: str
    tenant_id: str
    camera_id: str
    name: str
    ia_type: str  # "intrusion", "human_traffic", "vehicle_traffic", "lpr"
    polygon_points: list[list[float]]  # normalizados 0.0-1.0
    config: dict
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
