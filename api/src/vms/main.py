"""Ponto de entrada da aplicação VMS API."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from vms.core.config import get_settings
from vms.core.database import close_db, create_engine, init_db
from vms.core.event_bus import connect_event_bus, disconnect_event_bus
from vms.core.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Inicializa e finaliza recursos da aplicação."""
    settings = get_settings()

    # Banco de dados
    engine = create_engine(settings.database_url)
    init_db(engine)
    logger.info("Banco de dados inicializado")

    # Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
    )
    app.state.redis = redis_client
    app.state.arq_redis = aioredis.from_url(settings.redis_url)
    logger.info("Redis conectado")

    # RabbitMQ
    try:
        await connect_event_bus()
    except Exception as exc:
        logger.warning("Event bus indisponível no startup: %s", exc)

    yield

    # Shutdown
    await redis_client.aclose()
    await disconnect_event_bus()
    await close_db()
    logger.info("Recursos encerrados")


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI."""
    settings = get_settings()

    app = FastAPI(
        title="VMS API",
        description="Video Management System — Multi-tenant",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    origins = (
        ["*"]
        if not settings.is_production
        else [
            "https://app.vms.io",
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Handlers de exceção de domínio
    register_exception_handlers(app)

    # Handler genérico para erros não tratados
    @app.exception_handler(Exception)
    async def handle_unhandled(_req: Request, exc: Exception) -> JSONResponse:
        logger.exception("Erro não tratado: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": "Erro interno do servidor"},
        )

    _include_routers(app)
    return app


def _include_routers(app: FastAPI) -> None:
    """Registra todos os routers no app."""
    from vms.health.router import router as health_router
    from vms.iam.router import router as iam_router
    from vms.cameras.router import router as cameras_router
    from vms.events.router import router as events_router
    from vms.recordings.router import router as recordings_router
    from vms.notifications.router import router as notifications_router
    from vms.streaming.router import router as streaming_router
    from vms.sse.router import router as sse_router
    from vms.analytics_config.router import router as analytics_router
    from vms.analytics_config.router import internal_router as analytics_internal_router

    # Health — sem prefixo /api/v1
    app.include_router(health_router)

    # Endpoints internos — sem prefixo /api/v1 (chamados pelo analytics_service)
    app.include_router(analytics_internal_router)

    # Autenticação e gestão de usuários
    app.include_router(iam_router, prefix="/api/v1")

    # Recursos principais
    app.include_router(cameras_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(recordings_router, prefix="/api/v1")

    # Streaming auth (chamado pelo MediaMTX, sem prefixo /api/v1)
    app.include_router(streaming_router)

    # SSE
    app.include_router(sse_router, prefix="/api/v1")

    # Notificações
    app.include_router(notifications_router, prefix="/api/v1")

    # Analytics config — ROIs e configuração de análises
    app.include_router(analytics_router, prefix="/api/v1")


app = create_app()
