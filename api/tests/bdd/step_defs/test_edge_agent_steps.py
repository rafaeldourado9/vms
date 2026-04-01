"""BDD step definitions para Edge Agent — heartbeat, config, câmeras."""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from vms.cameras.models import CameraModel
from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/edge_agent.feature")


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


# ─── Given ────────────────────────────────────────────────────────────────────


@given(parsers.parse('um tenant "{name}" com slug "{slug}" existe'), target_fixture="ctx")
def create_tenant(bdd_session_factory, ctx, name, slug):
    """Cria tenant no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            tenant = TenantModel(id="t-bdd-ea", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-ea"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-ea",
                tenant_id=ctx["tenant_id"],
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name="Admin BDD EA",
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


@given(parsers.parse('existe um agent "{name}" no meu tenant com API key'))
def create_agent_with_key(bdd_client, ctx, name):
    """Cria agent via API e armazena API key."""
    resp = bdd_client.post(
        "/api/v1/agents",
        json={"name": name},
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    ctx["last_agent"] = data
    ctx["agent_api_key"] = data["api_key"]
    ctx["agent_id"] = data["id"]


@given(
    parsers.parse(
        'existe uma câmera "{name}" com URL RTSP "{rtsp_url}" no meu tenant'
    )
)
def create_camera(bdd_session_factory, ctx, name, rtsp_url):
    """Cria câmera no banco para o tenant."""
    import uuid

    camera_id = str(uuid.uuid4())

    async def _create():
        async with bdd_session_factory() as session:
            camera = CameraModel(
                id=camera_id,
                tenant_id=ctx["tenant_id"],
                name=name,
                rtsp_url=rtsp_url,
                manufacturer="generic",
                is_active=True,
                agent_id=ctx.get("agent_id"),
            )
            session.add(camera)
            await session.commit()

    _run(_create())
    ctx["camera_name"] = name
    ctx["camera_id"] = camera_id


@given("existe uma câmera inativa no meu tenant")
def create_inactive_camera(bdd_session_factory, ctx):
    """Cria câmera inativa no banco."""
    import uuid

    camera_id = str(uuid.uuid4())

    async def _create():
        async with bdd_session_factory() as session:
            camera = CameraModel(
                id=camera_id,
                tenant_id=ctx["tenant_id"],
                name="Câmera Inativa",
                rtsp_url="rtsp://inactive:554/live",
                manufacturer="generic",
                is_active=False,
            )
            session.add(camera)
            await session.commit()

    _run(_create())
    ctx["inactive_camera_id"] = camera_id


# ─── When ─────────────────────────────────────────────────────────────────────


@when(parsers.parse('o agent faz heartbeat com versão "{version}" e {streams:d} streams rodando'))
def do_heartbeat(bdd_client, ctx, version, streams):
    """Agent faz heartbeat via API key."""
    ctx["response"] = bdd_client.post(
        "/api/v1/agents/me/heartbeat",
        json={
            "version": version,
            "streams_running": streams,
            "streams_failed": 0,
            "uptime_seconds": 3600,
        },
        headers={"Authorization": f"ApiKey {ctx['agent_api_key']}"},
    )


@when("o agent busca sua configuração")
def do_get_config(bdd_client, ctx):
    """Agent busca configuração via API key."""
    ctx["response"] = bdd_client.get(
        "/api/v1/agents/me/config",
        headers={"Authorization": f"ApiKey {ctx['agent_api_key']}"},
    )


@when(parsers.parse('um agent faz heartbeat com API key "{key}"'))
def do_heartbeat_invalid(bdd_client, ctx, key):
    """Heartbeat com API key inválida."""
    ctx["response"] = bdd_client.post(
        "/api/v1/agents/me/heartbeat",
        json={
            "version": "1.0.0",
            "streams_running": 0,
            "streams_failed": 0,
            "uptime_seconds": 0,
        },
        headers={"Authorization": f"ApiKey {key}"},
    )


# ─── Then ─────────────────────────────────────────────────────────────────────


@then(parsers.parse('o agent fica com status "{expected_status}"'))
def check_agent_status(ctx, expected_status):
    """Verifica status do agent após heartbeat."""
    assert ctx["response"].status_code == 200
    assert ctx["response"].json()["status"] == expected_status


@then(parsers.parse('o agent reporta versão "{version}"'))
def check_agent_version(ctx, version):
    """Verifica versão reportada pelo agent."""
    assert ctx["response"].json()["version"] == version


@then("o agent recebe a lista de câmeras configuradas")
def check_agent_config(ctx):
    """Verifica que a config retorna estrutura correta."""
    assert ctx["response"].status_code == 200
    data = ctx["response"].json()
    assert "cameras" in data
    assert isinstance(data["cameras"], list)


@then(parsers.parse('a câmera "{name}" está na lista de configuração'))
def check_camera_in_config(ctx, name):
    """Verifica que câmera específica aparece na config."""
    data = ctx["response"].json()
    camera_names = [cam["name"] for cam in data.get("cameras", [])]
    assert name in camera_names


@then("a câmera inativa não aparece na lista de configuração")
def check_inactive_camera_absent(ctx):
    """Câmera inativa não deve aparecer na config do agent."""
    data = ctx["response"].json()
    camera_ids = [cam["id"] for cam in data.get("cameras", [])]
    assert ctx.get("inactive_camera_id") not in camera_ids


@then(parsers.parse("eu recebo erro {code:d}"))
def check_error_code(ctx, code):
    """Verifica código de erro HTTP."""
    assert ctx["response"].status_code == code
