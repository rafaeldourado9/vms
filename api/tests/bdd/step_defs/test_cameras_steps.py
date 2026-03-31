"""BDD step definitions para gerenciamento de câmeras (sync — pytest-bdd)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/cameras.feature")


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
            tenant = TenantModel(id="t-bdd-cam", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-cam"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-cam",
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
def create_existing_camera(bdd_client, ctx, name):
    """Cria câmera via API para usar em cenários seguintes."""
    with patch("vms.cameras.service.MediaMTXClient") as mock_cls:
        mock_cls.return_value = AsyncMock(
            add_path=AsyncMock(return_value=True),
            remove_path=AsyncMock(return_value=True),
        )
        resp = bdd_client.post(
            "/api/v1/cameras",
            json={
                "name": name,
                "rtsp_url": "rtsp://192.168.1.1:554/stream",
                "manufacturer": "generic",
            },
            headers={"Authorization": f"Bearer {ctx['access_token']}"},
        )
        assert resp.status_code == 201
        ctx.setdefault("cameras", []).append(resp.json())
        ctx["last_camera"] = resp.json()


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('eu crio uma câmera "{name}" com RTSP "{rtsp_url}"'))
def do_create_camera(bdd_client, ctx, name, rtsp_url):
    """Cria câmera via API."""
    with patch("vms.cameras.service.MediaMTXClient") as mock_cls:
        mock_cls.return_value = AsyncMock(add_path=AsyncMock(return_value=True))
        ctx["response"] = bdd_client.post(
            "/api/v1/cameras",
            json={
                "name": name,
                "rtsp_url": rtsp_url,
                "manufacturer": "hikvision",
            },
            headers={"Authorization": f"Bearer {ctx['access_token']}"},
        )


@when("eu listo as câmeras")
def do_list_cameras(bdd_client, ctx):
    """Lista câmeras via API."""
    ctx["response"] = bdd_client.get(
        "/api/v1/cameras",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu busco a câmera pelo ID")
def do_get_camera(bdd_client, ctx):
    """Busca câmera pelo ID da última câmera criada."""
    cam_id = ctx["last_camera"]["id"]
    ctx["response"] = bdd_client.get(
        f"/api/v1/cameras/{cam_id}",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when(parsers.parse('eu busco a câmera com ID "{camera_id}"'))
def do_get_camera_by_id(bdd_client, ctx, camera_id):
    """Busca câmera por ID específico."""
    ctx["response"] = bdd_client.get(
        f"/api/v1/cameras/{camera_id}",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )


@when("eu deleto a câmera")
def do_delete_camera(bdd_client, ctx):
    """Deleta a última câmera criada."""
    cam_id = ctx["last_camera"]["id"]
    with patch("vms.cameras.service.MediaMTXClient") as mock_cls:
        mock_cls.return_value = AsyncMock(remove_path=AsyncMock(return_value=True))
        ctx["response"] = bdd_client.delete(
            f"/api/v1/cameras/{cam_id}",
            headers={"Authorization": f"Bearer {ctx['access_token']}"},
        )


# ─── Then ────────────────────────────────────────────────────────────────────

@then("a câmera é criada com sucesso")
def check_camera_created(ctx):
    """Verifica status 201."""
    assert ctx["response"].status_code == 201


@then(parsers.parse('a câmera tem nome "{name}"'))
def check_camera_name(ctx, name):
    """Verifica nome da câmera."""
    assert ctx["response"].json()["name"] == name


@then("a câmera pertence ao meu tenant")
def check_camera_tenant(ctx):
    """Verifica tenant_id da câmera."""
    assert ctx["response"].json()["tenant_id"] == ctx["tenant_id"]


@then(parsers.parse("eu recebo {count:d} câmeras na lista"))
def check_camera_count(ctx, count):
    """Verifica quantidade de câmeras retornadas."""
    assert ctx["response"].status_code == 200
    assert len(ctx["response"].json()) == count


@then(parsers.parse('eu recebo os dados da câmera "{name}"'))
def check_camera_data(ctx, name):
    """Verifica dados da câmera retornada."""
    assert ctx["response"].status_code == 200
    assert ctx["response"].json()["name"] == name


@then(parsers.parse("eu recebo erro {code:d}"))
def check_error_code(ctx, code):
    """Verifica código de erro HTTP."""
    assert ctx["response"].status_code == code


@then("a câmera é removida com sucesso")
def check_camera_deleted(ctx):
    """Verifica status 204."""
    assert ctx["response"].status_code == 204
