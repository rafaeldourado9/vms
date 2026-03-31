"""Ponto de entrada do analytics_service — FastAPI app + lifespan."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from analytics.core.config import get_settings
from analytics.core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Inicializa e finaliza o orchestrator e plugins."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    await orchestrator.load_plugins()
    logger.info(
        "Analytics service iniciado com %d plugins",
        len(orchestrator.plugins),
    )

    yield

    await orchestrator.stop()
    logger.info("Analytics service encerrado")


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI do analytics_service."""
    application = FastAPI(
        title="VMS Analytics Service",
        description="Plugin-based video analytics for VMS",
        version="1.0.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    application.include_router(_build_router())
    return application


# ─── Schemas ────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Payload recebido de resultado de analytics."""

    plugin: str
    camera_id: str
    tenant_id: str
    roi_id: str
    event_type: str
    payload: dict
    occurred_at: str


class HealthResponse(BaseModel):
    """Resposta do health check."""

    status: str
    plugins_loaded: int
    plugin_names: list[str]


# ─── Router ─────────────────────────────────────────────────────────────────

def _build_router():  # noqa: ANN202
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        """Status dos plugins carregados."""
        plugins = orchestrator.plugins
        return HealthResponse(
            status="healthy",
            plugins_loaded=len(plugins),
            plugin_names=[p.name for p in plugins.values()],
        )

    @router.post(
        "/internal/analytics/ingest",
        status_code=status.HTTP_201_CREATED,
        tags=["internal"],
    )
    async def ingest_analytics(
        body: IngestRequest,
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> dict:
        """
        Recebe resultado de analytics e encaminha para a VMS API.

        Na arquitetura real, este endpoint está na VMS API.
        O analytics_service usa VMSClient para enviar resultados.
        Este endpoint é um proxy local para facilitar testes.
        """
        settings = get_settings()
        expected = f"ApiKey {settings.vms_analytics_api_key}"
        if not authorization or authorization != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Analytics API key inválida ou ausente",
            )

        logger.info(
            "Analytics ingest: plugin=%s camera=%s event=%s",
            body.plugin,
            body.camera_id,
            body.event_type,
        )
        return {"status": "accepted", "event_type": body.event_type}

    return router


app = create_app()
