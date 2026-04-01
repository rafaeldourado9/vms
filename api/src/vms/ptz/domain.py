"""Entidades de domínio PTZ (Pan-Tilt-Zoom)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PtzVector:
    """Vetor de velocidade/posição PTZ normalizado."""

    pan: float = 0.0    # -1.0 (esquerda) a 1.0 (direita)
    tilt: float = 0.0   # -1.0 (baixo)    a 1.0 (cima)
    zoom: float = 0.0   # 0.0  (afastado) a 1.0 (aproximado)


@dataclass
class PtzCommand:
    """Comando de movimento PTZ enviado à câmera."""

    camera_id: str
    tenant_id: str
    velocity: PtzVector = field(default_factory=PtzVector)
    timeout_seconds: int = 5    # Duração máxima do movimento contínuo


@dataclass
class PtzPreset:
    """Preset PTZ salvo na câmera (posição memorizada)."""

    token: str   # Identificador ONVIF do preset
    name: str    # Nome legível


@dataclass
class PtzCapabilities:
    """Capacidades PTZ reportadas pela câmera via ONVIF."""

    ptz_supported: bool
    can_continuous_move: bool = False
    can_absolute_move: bool = False
    can_relative_move: bool = False
    presets: list[PtzPreset] = field(default_factory=list)
