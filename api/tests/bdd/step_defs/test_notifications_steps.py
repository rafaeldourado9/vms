"""BDD step definitions para notificações (sync — pytest-bdd)."""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/notifications.feature")


def _run(coro):
    """Roda coroutine de forma síncrona."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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
            tenant = TenantModel(id="t-bdd-notif", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-notif"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-notif",
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


@given(parsers.parse('existe uma regra "{name}" para eventos "{pattern}"'))
def create_existing_rule(bdd_client, ctx, name, pattern):
    """Cria regra via API."""
    resp = bdd_client.post(
        "/api/v1/notifications/rules",
        json={
            "name": name,
            "event_type_pattern": pattern,
            "destination_url": "https://hooks.example.com/test",
            "webhook_secret": "test-secret-12345",
        },
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )
    assert resp.status_code == 201
    ctx["last_rule"] = resp.json()


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('eu crio uma regra "{name}" para eventos "{pattern}"'))
def do_create_rule(bdd_client, ctx, name, pattern):
    """Cria regra via API."""
    ctx["response"] = bdd_client.post(
        "/api/v1/notifications/rules",
        json={
            "name": name,
            "event_type_pattern": pattern,
            "destination_url": "https://hooks.example.com/test",
            "webhook_secret": "test-secret-12345",
        },
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu listo as regras de notificação")
def do_list_rules(bdd_client, ctx):
    """Lista regras via API."""
    ctx["response"] = bdd_client.get(
        "/api/v1/notifications/rules",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu deleto a regra")
def do_delete_rule(bdd_client, ctx):
    """Deleta última regra criada."""
    rule_id = ctx["last_rule"]["id"]
    ctx["response"] = bdd_client.delete(
        f"/api/v1/notifications/rules/{rule_id}",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


# ─── Then ────────────────────────────────────────────────────────────────────

@then("a regra é criada com sucesso")
def check_rule_created(ctx):
    """Verifica status 201."""
    assert ctx["response"].status_code == 201


@then("a regra está ativa")
def check_rule_active(ctx):
    """Verifica que a regra está ativa."""
    assert ctx["response"].json()["is_active"] is True


@then(parsers.parse("eu recebo pelo menos {count:d} regra na lista"))
def check_rule_count(ctx, count):
    """Verifica quantidade mínima de regras."""
    assert ctx["response"].status_code == 200
    assert len(ctx["response"].json()) >= count


@then("a regra é removida com sucesso")
def check_rule_deleted(ctx):
    """Verifica status 204."""
    assert ctx["response"].status_code == 204
