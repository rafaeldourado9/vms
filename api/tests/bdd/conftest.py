"""Fixtures para BDD — wraps async em sync para pytest-bdd."""
from __future__ import annotations

import asyncio
from typing import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from vms.core.database import Base, init_db

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _run(coro):
    """Roda coroutine de forma síncrona."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class SyncHttpClient:
    """Wrapper sync sobre httpx.AsyncClient para BDD steps."""

    def __init__(self, app):
        self._app = app

    def _make_client(self):
        transport = ASGITransport(app=self._app)
        return AsyncClient(transport=transport, base_url="http://test")

    def get(self, path, **kwargs):
        async def _do():
            async with self._make_client() as client:
                return await client.get(path, **kwargs)
        return _run(_do())

    def post(self, path, **kwargs):
        async def _do():
            async with self._make_client() as client:
                return await client.post(path, **kwargs)
        return _run(_do())

    def put(self, path, **kwargs):
        async def _do():
            async with self._make_client() as client:
                return await client.put(path, **kwargs)
        return _run(_do())

    def patch(self, path, **kwargs):
        async def _do():
            async with self._make_client() as client:
                return await client.patch(path, **kwargs)
        return _run(_do())

    def delete(self, path, **kwargs):
        async def _do():
            async with self._make_client() as client:
                return await client.delete(path, **kwargs)
        return _run(_do())


@pytest.fixture
def bdd_engine():
    """Engine SQLite para BDD."""
    engine = create_async_engine(_TEST_DB_URL, echo=False)

    _run(_setup_tables(engine))
    yield engine
    _run(_teardown_tables(engine))


async def _setup_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _teardown_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def bdd_session_factory(bdd_engine):
    """Factory de sessões para BDD."""
    return async_sessionmaker(
        bind=bdd_engine,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


@pytest.fixture
def bdd_client(bdd_engine, bdd_session_factory) -> SyncHttpClient:
    """HTTP client síncrono (wrapper) para BDD."""
    from unittest.mock import AsyncMock
    import redis.asyncio as aioredis
    from vms.main import create_app

    init_db(bdd_engine)
    test_app = create_app()

    async def override_get_db():
        async with bdd_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from vms.core.deps import get_db
    test_app.dependency_overrides[get_db] = override_get_db
    test_app.state.redis = AsyncMock(spec=aioredis.Redis)
    test_app.state.arq_redis = AsyncMock()

    return SyncHttpClient(test_app)
