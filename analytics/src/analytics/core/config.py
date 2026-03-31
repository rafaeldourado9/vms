"""Configurações do analytics_service via variáveis de ambiente."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas do ambiente ou .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─── VMS API ───────────────────────────────────────────────────────────
    vms_api_url: str = Field(default="http://localhost:8000")
    vms_analytics_api_key: str = Field(default="dev-analytics-key")

    # ─── Redis ─────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/1")

    # ─── MediaMTX ──────────────────────────────────────────────────────────
    mediamtx_api_url: str = Field(default="http://localhost:9997")

    # ─── Analytics ─────────────────────────────────────────────────────────
    analytics_fps: int = Field(default=1, description="Frames por segundo por câmera")
    analytics_workers: int = Field(default=4, description="Workers paralelos")
    yolo_imgsz: int = Field(default=640, description="Tamanho de imagem para YOLO")
    yolo_conf: float = Field(default=0.30, description="Confiança mínima YOLO")
    yolo_model_path: str = Field(default="/models/yolov8n.pt")
    lpr_model_path: str = Field(default="/models/yolov8n-plate.pt")

    # ─── Observabilidade ───────────────────────────────────────────────────
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Retorna settings cacheados (singleton)."""
    return Settings()
