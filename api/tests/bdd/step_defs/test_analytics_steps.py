"""BDD step definitions para analytics (ingestão + ROIs via API)."""
from __future__ import annotations

import asyncio

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from vms.cameras.models import CameraModel
from vms.core.security import hash_password
from vms.iam.models import TenantModel, UserModel

scenarios("../features/analytics.feature")


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
            tenant = TenantModel(id="t-bdd-analytics", name=name, slug=slug)
            session.add(tenant)
            await session.commit()

    _run(_create())
    ctx["tenant_id"] = "t-bdd-analytics"
    return ctx


@given(parsers.parse('um usuário admin "{email}" com senha "{password}" existe'))
def create_user(bdd_session_factory, ctx, email, password):
    """Cria usuário admin."""
    async def _create():
        async with bdd_session_factory() as session:
            user = UserModel(
                id="u-bdd-analytics",
                tenant_id=ctx["tenant_id"],
                email=email.lower(),
                hashed_password=hash_password(password),
                full_name="Admin BDD Analytics",
                role="admin",
            )
            session.add(user)
            await session.commit()

    _run(_create())
    ctx["email"] = email
    ctx["password"] = password


@given(parsers.parse('eu estou autenticado como "{email}"'))
def authenticate(bdd_client, ctx, email):
    """Autentica via /auth/token e salva access token."""
    resp = bdd_client.post(
        "/api/v1/auth/token",
        json={"email": email, "password": ctx["password"]},
    )
    assert resp.status_code == 200, f"Login falhou: {resp.text}"
    ctx["token"] = resp.json()["access_token"]
    ctx["auth_headers"] = {"Authorization": f"Bearer {ctx['token']}"}


@given(parsers.parse('existe uma câmera "{name}" no meu tenant'))
def create_camera(bdd_session_factory, ctx, name):
    """Cria câmera no banco."""
    async def _create():
        async with bdd_session_factory() as session:
            cam = CameraModel(
                id="cam-bdd-analytics",
                tenant_id=ctx["tenant_id"],
                name=name,
                rtsp_url="rtsp://192.168.1.100/stream",
                manufacturer="generic",
            )
            session.add(cam)
            await session.commit()

    _run(_create())
    ctx["camera_id"] = "cam-bdd-analytics"


@given(parsers.parse('existe uma ROI "{name}" do tipo "{ia_type}" para a câmera'))
def create_roi_given(bdd_client, ctx, name, ia_type):
    """Cria ROI via API."""
    resp = bdd_client.post(
        "/api/v1/analytics/rois",
        json={
            "camera_id": ctx["camera_id"],
            "name": name,
            "ia_type": ia_type,
            "polygon_points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            "config": {},
        },
        headers=ctx["auth_headers"],
    )
    assert resp.status_code == 201, f"Criar ROI falhou: {resp.text}"
    ctx["roi_id"] = resp.json()["id"]


# ─── When ────────────────────────────────────────────────────────────────────

@when(parsers.parse('eu crio uma ROI "{name}" do tipo "{ia_type}" para a câmera'))
def create_roi_when(bdd_client, ctx, name, ia_type):
    """Cria ROI via POST /analytics/rois."""
    resp = bdd_client.post(
        "/api/v1/analytics/rois",
        json={
            "camera_id": ctx["camera_id"],
            "name": name,
            "ia_type": ia_type,
            "polygon_points": [[0.0, 0.0], [0.5, 0.0], [0.5, 0.5], [0.0, 0.5]],
            "config": {"classes": [0], "min_confidence": 0.5, "cooldown_seconds": 30},
        },
        headers=ctx["auth_headers"],
    )
    ctx["last_response"] = resp
    if resp.status_code == 201:
        ctx["roi_id"] = resp.json()["id"]


@when("o analytics_service envia um resultado de intrusão para a câmera")
def ingest_analytics(bdd_client, ctx):
    """POST /internal/analytics/ingest com API key."""
    resp = bdd_client.post(
        "/internal/analytics/ingest",
        json={
            "plugin": "intrusion_detection",
            "camera_id": ctx["camera_id"],
            "tenant_id": ctx["tenant_id"],
            "roi_id": "roi-001",
            "event_type": "analytics.intrusion.detected",
            "payload": {"detection_count": 2, "roi_name": "Zona Proibida"},
            "occurred_at": "2026-03-30T12:00:00",
        },
        headers={"Authorization": "ApiKey dev-analytics-key"},
    )
    ctx["last_response"] = resp


@when("eu listo as ROIs do tenant")
def list_rois(bdd_client, ctx):
    """GET /analytics/rois."""
    resp = bdd_client.get(
        "/api/v1/analytics/rois",
        headers=ctx["auth_headers"],
    )
    ctx["last_response"] = resp


# ─── Then ────────────────────────────────────────────────────────────────────

@then("a ROI é criada com sucesso")
def roi_created(ctx):
    assert ctx["last_response"].status_code == 201


@then(parsers.parse('a ROI tem tipo "{ia_type}"'))
def roi_has_type(ctx, ia_type):
    data = ctx["last_response"].json()
    assert data["ia_type"] == ia_type


@then("o resultado é aceito com status 201")
def ingest_accepted(ctx):
    assert ctx["last_response"].status_code == 201, (
        f"Esperava 201, recebeu {ctx['last_response'].status_code}: {ctx['last_response'].text}"
    )


@then(parsers.parse("eu recebo pelo menos {count:d} ROI na lista"))
def roi_list_count(ctx, count):
    data = ctx["last_response"].json()
    assert len(data) >= count
