"""Configurações da aplicação via variáveis de ambiente."""

from functools import lru_cache

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas do ambiente ou arquivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ─── Ambiente ──────────────────────────────────────────────────────────
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    # ─── Banco de dados ────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://vms:vmsdev@localhost:5432/vms"
    )

    # ─── Redis ────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ─── RabbitMQ ─────────────────────────────────────────────────────────
    rabbitmq_url: str = Field(default="amqp://vms:vmsdev@localhost:5672/")

    # ─── Segurança ────────────────────────────────────────────────────────
    secret_key: str = Field(default="dev-secret-change-in-production")
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=7)

    # ─── MediaMTX ─────────────────────────────────────────────────────────
    mediamtx_api_url: str = Field(default="http://localhost:9997")
    mediamtx_rtmp_url: str = Field(default="rtmp://localhost:1935")

    # ─── Analytics ────────────────────────────────────────────────────────
    analytics_api_key: str = Field(default="dev-analytics-key")

    # ─── Gravações ────────────────────────────────────────────────────────
    recordings_path: str = Field(default="/recordings")

    # ─── ALPR ─────────────────────────────────────────────────────────────
    alpr_dedup_ttl_seconds: int = Field(default=60)

    # ─── Limites ──────────────────────────────────────────────────────────
    max_cameras: int = Field(default=200)

    @field_validator("environment")
    @classmethod
    def validar_ambiente(cls, v: str) -> str:
        """Valida que o ambiente é um valor conhecido."""
        ambientes_validos = {"development", "staging", "production"}
        if v not in ambientes_validos:
            raise ValueError(f"Ambiente deve ser um de: {ambientes_validos}")
        return v

    @property
    def is_production(self) -> bool:
        """Retorna True se o ambiente for produção."""
        return self.environment == "production"

    @property
    def database_url_sync(self) -> str:
        """URL síncrona do banco (para Alembic)."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


@lru_cache
def get_settings() -> Settings:
    """Retorna instância singleton de Settings."""
    return Settings()
