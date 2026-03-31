"""BDD step definitions para ALPR (sync — pytest-bdd)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytest_bdd import given, when, then, scenarios, parsers

from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel
from vms.cameras.models import CameraModel

scenarios("../features/alpr.feature")


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
            tenant = TenantModel(id="t-bdd-alpr", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-alpr"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-alpr",
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
    """Cria câmera diretamente no banco."""
    camera_id = "c-bdd-alpr"

    async def _create():
        async with bdd_session_factory() as session:
            camera = CameraModel(
                id=camera_id,
                tenant_id=ctx["tenant_id"],
                name=name,
                rtsp_url="rtsp://192.168.1.1:554/stream",
                manufacturer="hikvision",
            )
            session.add(camera)
            await session.commit()

    _run(_create())
    ctx["camera_id"] = camera_id


@given(parsers.parse('uma detecção ALPR com placa "{plate}" já foi aceita'))
def create_first_detection(bdd_client, ctx, plate):
    """Envia primeira detecção ALPR que é aceita."""
    with patch("vms.core.event_bus.publish_event", new_callable=AsyncMock):
        # Mock Redis para aceitar (SET NX retorna True)
        bdd_client._app.state.redis.set = AsyncMock(return_value=True)
        resp = bdd_client.post(
            "/api/v1/webhooks/alpr",
            json={
                "camera_id": ctx["camera_id"],
                "plate": plate,
                "confidence": 0.95,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        assert resp.status_code == 202
        assert resp.json()["accepted"] is True
        ctx["dedup_plate"] = plate


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('uma detecção ALPR com placa "{plate}" e confiança {conf} é recebida'))
def do_alpr_detection(bdd_client, ctx, plate, conf):
    """Envia detecção ALPR via webhook vendor (resolve tenant corretamente)."""
    with patch("vms.core.event_bus.publish_event", new_callable=AsyncMock):
        bdd_client._app.state.redis.set = AsyncMock(return_value=True)
        ctx["response"] = bdd_client.post(
            "/api/v1/webhooks/alpr/hikvision",
            json={
                "ANPR": {
                    "licensePlate": plate,
                    "confidenceLevel": int(float(conf) * 100),
                    "dateTime": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S"),
                },
            },
            params={
                "camera_id": ctx["camera_id"],
                "tenant_id": ctx["tenant_id"],
            },
        )


@when(parsers.parse('uma segunda detecção com placa "{plate}" é recebida dentro do TTL'))
def do_duplicate_detection(bdd_client, ctx, plate):
    """Envia detecção duplicada (Redis retorna None = duplicata)."""
    with patch("vms.core.event_bus.publish_event", new_callable=AsyncMock):
        bdd_client._app.state.redis.set = AsyncMock(return_value=None)
        ctx["response"] = bdd_client.post(
            "/api/v1/webhooks/alpr",
            json={
                "camera_id": ctx["camera_id"],
                "plate": plate,
                "confidence": 0.95,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )


@when(parsers.parse('uma detecção ALPR do fabricante "{manufacturer}" é recebida'))
def do_vendor_detection(bdd_client, ctx, manufacturer):
    """Envia detecção para fabricante específico."""
    ctx["response"] = bdd_client.post(
        f"/api/v1/webhooks/alpr/{manufacturer}",
        json={"some": "data"},
        params={
            "camera_id": ctx["camera_id"],
            "tenant_id": ctx["tenant_id"],
        },
    )


# ─── Then ────────────────────────────────────────────────────────────────────

@then("o evento é aceito")
def check_event_accepted(ctx):
    """Verifica que detecção foi aceita."""
    assert ctx["response"].status_code == 202
    assert ctx["response"].json()["accepted"] is True


@then("o evento aparece na listagem de eventos")
def check_event_in_list(bdd_client, ctx):
    """Verifica que evento aparece na API de listagem."""
    resp = bdd_client.get(
        "/api/v1/events",
        headers={"Authorization": f"Bearer {ctx['access_token']}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@then("a detecção é ignorada como duplicata")
def check_duplicate_ignored(ctx):
    """Verifica que duplicata retorna accepted=False."""
    assert ctx["response"].status_code == 202
    assert ctx["response"].json()["accepted"] is False


@then(parsers.parse("eu recebo erro {code:d}"))
def check_error_code(ctx, code):
    """Verifica código de erro HTTP."""
    assert ctx["response"].status_code == code
