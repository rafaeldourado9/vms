"""Fixtures para testes E2E — requer docker-compose up."""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from vms.infrastructure.database import Base, init_db
from vms.infrastructure.security import hash_password, create_access_token
from vms.iam.models import TenantModel, UserModel
from vms.cameras.models import CameraModel

# Importar todos os models necessários
import vms.events.models  # noqa: F401
import vms.recordings.models  # noqa: F401
import vms.notifications.models  # noqa: F401
import vms.streaming.models  # noqa: F401
import vms.analytics.models  # noqa: F401
import vms.audit.models  # noqa: F401

E2E_BASE_URL = os.environ.get("VMS_BASE_URL", "http://localhost:8000")
E2E_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://vms:vmsdev@localhost:5432/vms",
)


@pytest.fixture(scope="session")
def e2e_engine():
    """Engine PostgreSQL real para E2E."""
    engine = create_async_engine(E2E_DB_URL, echo=False)
    yield engine


@pytest.fixture
async def e2e_session(e2e_engine) -> AsyncSession:
    """Sessão isolada — rollback ao final."""
    factory = async_sessionmaker(
        bind=e2e_engine, expire_on_commit=False, autoflush=False, autocommit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def e2e_data(e2e_session: AsyncSession) -> dict:
    """Cria tenant + user + câmera únicos para o teste e devolve token + IDs."""
    uid = uuid.uuid4().hex[:8]
    tenant_id = f"t-e2e-{uid}"
    user_id = f"u-e2e-{uid}"
    camera_id = f"c-e2e-{uid}"
    email = f"e2e-{uid}@chain.test"
    password = "senha12345"

    tenant = TenantModel(id=tenant_id, name=f"E2E Chain {uid}", slug=f"e2e-chain-{uid}")
    e2e_session.add(tenant)
    await e2e_session.flush()

    user = UserModel(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password(password),
        full_name="E2E Admin",
        role="admin",
    )
    e2e_session.add(user)

    camera = CameraModel(
        id=camera_id,
        tenant_id=tenant_id,
        name="Cam E2E Chain",
        rtsp_url="rtsp://192.168.1.200:554/stream",
        manufacturer="generic",
    )
    e2e_session.add(camera)
    await e2e_session.commit()

    token = create_access_token(user_id, tenant_id, "admin")
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "camera_id": camera_id,
        "token": token,
        "mediamtx_path": f"tenant-{tenant_id}/cam-{camera_id}",
    }


@pytest.fixture
async def e2e_client() -> httpx.AsyncClient:
    """Cliente HTTP assíncrono apontando para a API real em docker."""
    async with httpx.AsyncClient(base_url=E2E_BASE_URL, timeout=30.0) as client:
        yield client
