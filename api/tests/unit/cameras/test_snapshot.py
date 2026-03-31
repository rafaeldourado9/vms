"""Testes unitários do módulo cameras/snapshot.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from vms.cameras.domain import Camera, CameraManufacturer, StreamProtocol
from vms.cameras.snapshot import get_snapshot_url


def _cam(**kwargs) -> Camera:
    defaults = dict(id="c1", tenant_id="t1", name="Cam", manufacturer=CameraManufacturer.GENERIC)
    defaults.update(kwargs)
    return Camera(**defaults)


class TestGetSnapshotUrl:
    """Testes da função get_snapshot_url."""

    async def test_onvif_with_snapshot_url(self):
        """Câmera ONVIF retorna snapshot URL obtida via GetSnapshotUri."""
        from vms.cameras.domain import OnvifProbeResult

        camera = _cam(
            stream_protocol=StreamProtocol.ONVIF,
            onvif_url="http://192.168.1.10/onvif/device_service",
            onvif_username="admin",
            onvif_password="pass",
        )
        probe_result = OnvifProbeResult(
            reachable=True,
            snapshot_url="http://192.168.1.10/Streaming/Channels/1/picture",
        )
        with patch(
            "vms.cameras.onvif_client.OnvifClient.probe",
            AsyncMock(return_value=probe_result),
        ):
            url = await get_snapshot_url(camera)

        assert url == "http://192.168.1.10/Streaming/Channels/1/picture"

    async def test_onvif_fallback_to_rtsp_proxy(self):
        """Câmera ONVIF sem snapshot URL cai para proxy RTSP."""
        from vms.cameras.domain import OnvifProbeResult

        camera = _cam(
            stream_protocol=StreamProtocol.ONVIF,
            onvif_url="http://192.168.1.10/onvif/device_service",
            onvif_username="admin",
            onvif_password="pass",
            rtsp_url="rtsp://192.168.1.10:554/stream",
        )
        probe_result = OnvifProbeResult(reachable=True, snapshot_url=None)
        with patch(
            "vms.cameras.onvif_client.OnvifClient.probe",
            AsyncMock(return_value=probe_result),
        ):
            url = await get_snapshot_url(camera)

        assert url is not None
        assert "tenant-t1/cam-c1" in url

    async def test_rtsp_pull_returns_proxy_url(self):
        """Câmera RTSP pull retorna URL de proxy interno."""
        camera = _cam(
            stream_protocol=StreamProtocol.RTSP_PULL,
            rtsp_url="rtsp://192.168.1.5:554/h264",
        )
        url = await get_snapshot_url(camera)

        assert url is not None
        assert "tenant-t1/cam-c1" in url

    async def test_rtmp_push_no_rtsp_url_returns_none(self):
        """Câmera RTMP push sem rtsp_url retorna None."""
        camera = _cam(
            stream_protocol=StreamProtocol.RTMP_PUSH,
            rtmp_stream_key="abc123",
        )
        url = await get_snapshot_url(camera)
        assert url is None
