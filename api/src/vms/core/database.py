"""Configuração do SQLAlchemy async e gerenciamento de sessões."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from vms.core.config import get_settings


class Base(DeclarativeBase):
    """Base para todos os modelos ORM."""

    pass


# Instâncias globais — inicializadas no lifespan da aplicação
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Cria engine assíncrono com configurações para produção."""
    settings = get_settings()
    url = database_url or settings.database_url

    return create_async_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.debug,
    )


def init_db(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Inicializa a fábrica de sessões."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    return _session_factory


async def close_db() -> None:
    """Fecha a engine (chamado no shutdown da aplicação)."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Retorna a fábrica de sessões. Lança erro se não inicializada."""
    if _session_factory is None:
        raise RuntimeError("Banco de dados não inicializado. Chame init_db() primeiro.")
    return _session_factory


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para criar sessão com commit/rollback automático."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
