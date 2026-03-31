"""BDD step definitions para autenticação (sync — pytest-bdd requer isso)."""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/auth.feature")


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

@given(parsers.parse('um tenant "{name}" com slug "{slug}" existe'))
def create_tenant(bdd_session_factory, ctx, name, slug):
    async def _create():
        async with bdd_session_factory() as session:
            tenant = TenantModel(id="t-bdd", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd"


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd",
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
    resp = bdd_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": ctx["user_password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    ctx["access_token"] = data["access_token"]
    ctx["refresh_token"] = data["refresh_token"]


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('eu faço login com email "{email}" e senha "{password}"'))
def do_login(bdd_client, ctx, email, password):
    ctx["response"] = bdd_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": password},
    )


@when("eu renovo meu token com o refresh token")
def do_refresh(bdd_client, ctx):
    ctx["response"] = bdd_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": ctx["refresh_token"]},
    )


@when(parsers.parse('eu acesso GET "{path}" sem token'))
def access_without_token(bdd_client, ctx, path):
    ctx["response"] = bdd_client.get(path)


@when(parsers.parse('eu acesso GET "{path}" com meu token'))
def access_with_token(bdd_client, ctx, path):
    ctx["response"] = bdd_client.get(
        path,
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


# ─── Then ────────────────────────────────────────────────────────────────────

@then("eu recebo um access token válido")
def check_access_token(ctx):
    data = ctx["response"].json()
    assert "access_token" in data
    assert len(data["access_token"]) > 20


@then("eu recebo um refresh token válido")
def check_refresh_token(ctx):
    data = ctx["response"].json()
    assert "refresh_token" in data
    assert len(data["refresh_token"]) > 20


@then(parsers.parse("eu recebo erro {code:d}"))
def check_error_code(ctx, code):
    assert ctx["response"].status_code == code


@then("eu recebo um novo access token")
def check_new_access(ctx):
    data = ctx["response"].json()
    assert "access_token" in data


@then("eu recebo um novo refresh token")
def check_new_refresh(ctx):
    data = ctx["response"].json()
    assert "refresh_token" in data


@then(parsers.parse('eu recebo os dados do usuário "{email}"'))
def check_user_data(ctx, email):
    data = ctx["response"].json()
    assert data["email"] == email.lower()
