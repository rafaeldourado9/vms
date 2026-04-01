"""Testes de integração do endpoint VOD /cameras/{id}/vod."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from vms.cameras.domain import Camera, CameraManufacturer, StreamProtocol


def _make_camera(tenant_id: str, camera_id: str) -> Camera:
    return Camera(
        id=camera_id,
        tenant_id=tenant_id,
        name="Câmera VOD",
        manufacturer=CameraManufacturer.GENERIC,
        stream_protocol=StreamProtocol.RTSP_PULL,
        rtsp_url="rtsp://x",
    )


@pytest.fixture
def headers(auth_headers):
    return {
        "Authorization": auth_headers["Authorization"],
        "X-MediaMTX-Host": "mediamtx.local",
    }


@pytest.fixture
def tenant_id(auth_headers):
    return auth_headers["_tenant_id"]


class TestVodEndpoint:
    async def test_vod_sem_gravacoes_retorna_404(self, client: AsyncClient, headers, tenant_id):
        """Sem segmentos no período → 404."""
        camera_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        from_ts = (now - timedelta(hours=1)).isoformat()
        to_ts = now.isoformat()

        with (
            patch("vms.recordings.router.CameraService") as mock_svc_cls,
            patch("vms.recordings.router.RecordingSegmentRepository") as mock_repo_cls,
        ):
            mock_cam_svc = AsyncMock()
            mock_cam_svc.get_camera.return_value = _make_camera(tenant_id, camera_id)
            mock_svc_cls.return_value = mock_cam_svc

            mock_repo = AsyncMock()
            mock_repo.list_by_camera.return_value = ([], 0)
            mock_repo_cls.return_value = mock_repo

            resp = await client.get(
                f"/api/v1/cameras/{camera_id}/vod",
                params={"from": from_ts, "to": to_ts},
                headers=headers,
            )

        assert resp.status_code == 404

    async def test_vod_com_gravacoes_retorna_hls_url(self, client: AsyncClient, headers, tenant_id):
        """Com segmentos disponíveis → retorna VodResponse com hls_url."""
        from vms.recordings.domain import RecordingSegment

        camera_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        from_ts = now - timedelta(hours=1)
        to_ts = now

        seg = RecordingSegment(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path=f"tenant-{tenant_id}/cam-{camera_id}",
            file_path="/recordings/x.mp4",
            started_at=from_ts,
            ended_at=from_ts + timedelta(seconds=60),
            duration_seconds=60.0,
            size_bytes=1_000_000,
        )

        with (
            patch("vms.recordings.router.CameraService") as mock_svc_cls,
            patch("vms.recordings.router.RecordingSegmentRepository") as mock_repo_cls,
            patch("vms.recordings.router.AuthService") as mock_auth_cls,
        ):
            mock_cam_svc = AsyncMock()
            mock_cam_svc.get_camera.return_value = _make_camera(tenant_id, camera_id)
            mock_svc_cls.return_value = mock_cam_svc

            mock_repo = AsyncMock()
            mock_repo.list_by_camera.return_value = ([seg], 1)
            mock_repo_cls.return_value = mock_repo

            mock_auth = AsyncMock()
            mock_auth.issue_viewer_token.return_value = "viewer-token-abc"
            mock_auth_cls.return_value = mock_auth

            resp = await client.get(
                f"/api/v1/cameras/{camera_id}/vod",
                params={"from": from_ts.isoformat(), "to": to_ts.isoformat()},
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "hls_url" in data
        assert "mediamtx.local" in data["hls_url"]
        assert "rec.m3u8" in data["hls_url"]
        assert "viewer-token-abc" in data["hls_url"]
        assert data["segments_count"] == 1
        assert data["has_gaps"] is False

    async def test_vod_detecta_gap(self, client: AsyncClient, headers, tenant_id):
        """Dois segmentos com gap > 5s → has_gaps=true."""
        from vms.recordings.domain import RecordingSegment

        camera_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        from_ts = now - timedelta(hours=2)
        to_ts = now

        seg1 = RecordingSegment(
            id=str(uuid.uuid4()), tenant_id=tenant_id, camera_id=camera_id,
            mediamtx_path="x", file_path="/r/a.mp4",
            started_at=from_ts,
            ended_at=from_ts + timedelta(seconds=60),
            duration_seconds=60.0, size_bytes=0,
        )
        # gap de 5 minutos
        seg2 = RecordingSegment(
            id=str(uuid.uuid4()), tenant_id=tenant_id, camera_id=camera_id,
            mediamtx_path="x", file_path="/r/b.mp4",
            started_at=from_ts + timedelta(minutes=6),
            ended_at=from_ts + timedelta(minutes=7),
            duration_seconds=60.0, size_bytes=0,
        )

        with (
            patch("vms.recordings.router.CameraService") as mock_svc_cls,
            patch("vms.recordings.router.RecordingSegmentRepository") as mock_repo_cls,
            patch("vms.recordings.router.AuthService") as mock_auth_cls,
        ):
            mock_cam_svc = AsyncMock()
            mock_cam_svc.get_camera.return_value = _make_camera(tenant_id, camera_id)
            mock_svc_cls.return_value = mock_cam_svc

            mock_repo = AsyncMock()
            mock_repo.list_by_camera.return_value = ([seg1, seg2], 2)
            mock_repo_cls.return_value = mock_repo

            mock_auth = AsyncMock()
            mock_auth.issue_viewer_token.return_value = "token"
            mock_auth_cls.return_value = mock_auth

            resp = await client.get(
                f"/api/v1/cameras/{camera_id}/vod",
                params={"from": from_ts.isoformat(), "to": to_ts.isoformat()},
                headers=headers,
            )

        assert resp.status_code == 200
        assert resp.json()["has_gaps"] is True

    async def test_vod_sem_auth_retorna_401(self, client: AsyncClient):
        """Sem JWT → 401."""
        resp = await client.get(
            "/api/v1/cameras/any/vod",
            params={"from": "2026-04-01T00:00:00Z", "to": "2026-04-01T01:00:00Z"},
        )
        assert resp.status_code == 401
