"""BDD step definitions para gerenciamento de agents (sync — pytest-bdd)."""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/agents.feature")


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
            tenant = TenantModel(id="t-bdd-ag", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-ag"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-ag",
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


@given(parsers.parse('existe um agent "{name}" no meu tenant'))
def create_existing_agent(bdd_client, ctx, name):
    """Cria agent via API."""
    resp = bdd_client.post(
        "/api/v1/agents",
        json={"name": name},
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )
    assert resp.status_code == 201
    ctx.setdefault("agents", []).append(resp.json())
    ctx["last_agent"] = resp.json()


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


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('eu crio um agent "{name}"'))
def do_create_agent(bdd_client, ctx, name):
    """Cria agent via API."""
    ctx["response"] = bdd_client.post(
        "/api/v1/agents",
        json={"name": name},
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu listo os agents")
def do_list_agents(bdd_client, ctx):
    """Lista agents via API."""
    ctx["response"] = bdd_client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when(parsers.parse('o agent faz heartbeat com versão "{version}" e {streams:d} streams rodando'))
def do_heartbeat(bdd_client, ctx, version, streams):
    """Agent faz heartbeat via API key."""
    ctx["response"] = bdd_client.post(
        "/api/v1/agents/me/heartbeat",
        json={
            "version": version,
            "streams_running": streams,
            "streams_failed": 0,
            "uptime_seconds": 1234,
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


# ─── Then ────────────────────────────────────────────────────────────────────

@then("o agent é criado com sucesso")
def check_agent_created(ctx):
    """Verifica status 201."""
    assert ctx["response"].status_code == 201


@then(parsers.parse('eu recebo uma API key que começa com "{prefix}"'))
def check_api_key_prefix(ctx, prefix):
    """Verifica prefixo da API key."""
    data = ctx["response"].json()
    assert "api_key" in data
    assert data["api_key"].startswith(prefix)


@then(parsers.parse("eu recebo pelo menos {count:d} agent na lista"))
def check_agent_count(ctx, count):
    """Verifica quantidade mínima de agents."""
    assert ctx["response"].status_code == 200
    assert len(ctx["response"].json()) >= count


@then(parsers.parse('o agent fica com status "{expected_status}"'))
def check_agent_status(ctx, expected_status):
    """Verifica status do agent."""
    assert ctx["response"].status_code == 200
    assert ctx["response"].json()["status"] == expected_status


@then(parsers.parse('o agent reporta versão "{version}"'))
def check_agent_version(ctx, version):
    """Verifica versão reportada pelo agent."""
    assert ctx["response"].json()["version"] == version


@then("o agent recebe a lista de câmeras configuradas")
def check_agent_config(ctx):
    """Verifica que configuração retorna lista de câmeras."""
    assert ctx["response"].status_code == 200
    data = ctx["response"].json()
    assert "agent_id" in data
    assert "cameras" in data
    assert isinstance(data["cameras"], list)


@then(parsers.parse("eu recebo erro {code:d}"))
def check_error_code(ctx, code):
    """Verifica código de erro HTTP."""
    assert ctx["response"].status_code == code
