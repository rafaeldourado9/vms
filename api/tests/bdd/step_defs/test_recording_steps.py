"""BDD step definitions para gravações e clipes (sync — pytest-bdd)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel
from vms.cameras.models import CameraModel

scenarios("../features/recording.feature")


def _run(coro):
    """Roda coroutine de forma síncrona."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ─── State container ──────────────────────────────────────────────────────────

@pytest.fixture
def ctx():
    """Contexto compartilhado entre steps."""
    return {}


# ─── Given ───────────────────────────────────────────────────────────────────

@given(parsers.parse('um tenant "{name}" com slug "{slug}" existe'), target_fixture="ctx")
def create_tenant(bdd_session_factory, ctx, name, slug):
    """Cria tenant no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            tenant = TenantModel(id="t-bdd-rec", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-rec"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-rec",
                tenant_id=ctx["tenant_id"],
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name="Admin BDD",
                role="admin",
            )
            session.add(user)
            await session.commit()

    _run(_create())
    ctx["user_email"] = email
    ctx["user_password"] = password


@given(parsers.parse('eu estou autenticado como "{email}"'))
def authenticate(bdd_client, ctx, email):
    """Autentica e armazena token."""
    resp = bdd_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": ctx["user_password"]},
    )
    assert resp.status_code == 200
    ctx["access_token"] = resp.json()["access_token"]


@given(parsers.parse('existe uma câmera "{name}" no meu tenant'))
def create_camera(bdd_session_factory, ctx, name):
    """Cria câmera diretamente no banco (evita mock de MediaMTX)."""
    camera_id = "c-bdd-rec"

    async def _create():
        async with bdd_session_factory() as session:
            camera = CameraModel(
                id=camera_id,
                tenant_id=ctx["tenant_id"],
                name=name,
                rtsp_url="rtsp://192.168.1.1:554/stream",
                manufacturer="generic",
            )
            session.add(camera)
            await session.commit()

    _run(_create())
    ctx["camera_id"] = camera_id


@given("eu solicitei um clipe dos últimos 5 minutos")
def create_clip_given(bdd_client, ctx):
    """Cria clipe via API."""
    now = datetime.now(UTC)
    resp = bdd_client.post(
        "/api/v1/recordings/clips",
        json={
            "camera_id": ctx["camera_id"],
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": now.isoformat(),
        },
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )
    assert resp.status_code == 201
    ctx["last_clip"] = resp.json()


# ─── When ────────────────────────────────────────────────────────────────────

@when("eu listo os segmentos da câmera")
def do_list_segments(bdd_client, ctx):
    """Lista segmentos via API."""
    ctx["response"] = bdd_client.get(
        "/api/v1/recordings",
        params={"camera_id": ctx["camera_id"]},
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu solicito um clipe dos últimos 5 minutos")
def do_create_clip(bdd_client, ctx):
    """Solicita clipe via API."""
    now = datetime.now(UTC)
    ctx["response"] = bdd_client.post(
        "/api/v1/recordings/clips",
        json={
            "camera_id": ctx["camera_id"],
            "starts_at": (now - timedelta(minutes=5)).isoformat(),
            "ends_at": now.isoformat(),
        },
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu listo os clipes")
def do_list_clips(bdd_client, ctx):
    """Lista clipes via API."""
    ctx["response"] = bdd_client.get(
        "/api/v1/recordings/clips",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


# ─── Then ────────────────────────────────────────────────────────────────────

@then("eu recebo lista vazia de segmentos")
def check_empty_segments(ctx):
    """Verifica lista vazia."""
    assert ctx["response"].status_code == 200
    assert ctx["response"].json()["total"] == 0


@then(parsers.parse('o clipe é criado com status "{expected_status}"'))
def check_clip_status(ctx, expected_status):
    """Verifica status do clipe."""
    assert ctx["response"].status_code == 201
    assert ctx["response"].json()["status"] == expected_status


@then("o clipe pertence à câmera correta")
def check_clip_camera(ctx):
    """Verifica camera_id do clipe."""
    assert ctx["response"].json()["camera_id"] == ctx["camera_id"]


@then(parsers.parse("eu recebo pelo menos {count:d} clipe na lista"))
def check_clip_count(ctx, count):
    """Verifica quantidade mínima de clipes."""
    assert ctx["response"].status_code == 200
    assert ctx["response"].json()["total"] >= count
