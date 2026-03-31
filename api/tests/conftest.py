"""Fixtures compartilhadas para todos os testes."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from vms.core.database import Base, init_db, get_session_factory
from vms.core.config import Settings, get_settings
from vms.iam.domain import ApiKey, ApiKeyOwnerType, Tenant, User, UserRole
from vms.core.security import hash_password, create_access_token

# Importar todos os models para que Base.metadata tenha todas as tabelas
import vms.iam.models  # noqa: F401
import vms.cameras.models  # noqa: F401
import vms.events.models  # noqa: F401
import vms.recordings.models  # noqa: F401
import vms.notifications.models  # noqa: F401
import vms.streaming.models  # noqa: F401
import vms.analytics_config.models  # noqa: F401


# ─── Settings override para testes ────────────────────────────────────────────

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Settings para testes usando SQLite in-memory."""
    return Settings(
        database_url=_TEST_DB_URL,
        redis_url="redis://localhost:6379/15",
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        secret_key="test-secret-key-do-not-use-in-prod",
        environment="development",
    )


# ─── Database ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Engine SQLite async in-memory para testes."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Sessão de banco isolada para cada teste."""
    factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def db_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Factory de sessões para usar no app override."""
    return async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


# ─── HTTP Client (integração) ─────────────────────────────────────────────────

@pytest.fixture
async def app(db_engine: AsyncEngine, db_session_factory):
    """FastAPI app com DB em memória e sem RabbitMQ/Redis."""
    from unittest.mock import patch, AsyncMock
    import redis.asyncio as aioredis
    from vms.main import create_app

    # Override database
    init_db(db_engine)

    test_app = create_app()

    # Override get_db dependency
    async def override_get_db():
        async with db_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from vms.core.deps import get_db
    test_app.dependency_overrides[get_db] = override_get_db

    # Mock Redis no state
    test_app.state.redis = AsyncMock(spec=aioredis.Redis)
    test_app.state.arq_redis = AsyncMock()

    yield test_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client async para testes de integração."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Dados de teste ───────────────────────────────────────────────────────────

@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def make_tenant():
    """Factory para criar entidades Tenant de teste."""
    def _make(**kwargs) -> Tenant:
        defaults = {
            "id": str(uuid.uuid4()),
            "name": "Test Tenant",
            "slug": "test-tenant",
            "is_active": True,
        }
        defaults.update(kwargs)
        return Tenant(**defaults)
    return _make


@pytest.fixture
def make_user():
    """Factory para criar entidades User de teste."""
    def _make(**kwargs) -> User:
        defaults = {
            "id": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "email": "user@test.com",
            "hashed_password": hash_password("senha12345"),
            "full_name": "Test User",
            "role": UserRole.ADMIN,
            "is_active": True,
        }
        defaults.update(kwargs)
        return User(**defaults)
    return _make


@pytest.fixture
def auth_headers(make_tenant, make_user):
    """Headers com JWT válido para testes de integração."""
    tenant = make_tenant()
    user = make_user(tenant_id=tenant.id)
    token = create_access_token(user.id, tenant.id, user.role.value)
    return {
        "Authorization": f"Bearer {token}",
        "_tenant_id": tenant.id,
        "_user_id": user.id,
    }
