"""Testes unitários do OnvifClient (mock de respostas SOAP/HTTP)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vms.cameras.onvif_client import OnvifClient


DEVICE_INFO_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <tds:GetDeviceInformationResponse xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
      <tds:Manufacturer>Hikvision</tds:Manufacturer>
      <tds:Model>DS-2CD2143G2-I</tds:Model>
      <tds:FirmwareVersion>V5.7.7</tds:FirmwareVersion>
    </tds:GetDeviceInformationResponse>
  </s:Body>
</s:Envelope>"""

PROFILES_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetProfilesResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:Profiles token="Profile_1" fixed="true">
        <tt:Name xmlns:tt="http://www.onvif.org/ver10/schema">MainStream</tt:Name>
      </trt:Profiles>
    </trt:GetProfilesResponse>
  </s:Body>
</s:Envelope>"""

STREAM_URI_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetStreamUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:MediaUri>
        <tt:Uri xmlns:tt="http://www.onvif.org/ver10/schema">rtsp://192.168.1.10:554/Streaming/Channels/1</tt:Uri>
      </trt:MediaUri>
    </trt:GetStreamUriResponse>
  </s:Body>
</s:Envelope>"""

SNAPSHOT_URI_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetSnapshotUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
      <trt:MediaUri>
        <tt:Uri xmlns:tt="http://www.onvif.org/ver10/schema">http://192.168.1.10/Streaming/Channels/1/picture</tt:Uri>
      </trt:MediaUri>
    </trt:GetSnapshotUriResponse>
  </s:Body>
</s:Envelope>"""


def _mock_response(text: str, status_code: int = 200):
    r = MagicMock()
    r.status_code = status_code
    r.text = text
    return r


class TestOnvifClientProbe:
    """Testes do método OnvifClient.probe."""

    async def test_probe_success(self):
        """Probe retorna dados completos quando câmera responde."""
        responses = [
            _mock_response(DEVICE_INFO_RESPONSE),
            _mock_response(PROFILES_RESPONSE),
            _mock_response(STREAM_URI_RESPONSE),
            _mock_response(SNAPSHOT_URI_RESPONSE),
        ]

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=responses)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("vms.cameras.onvif_client.httpx.AsyncClient", return_value=mock_client):
            result = await OnvifClient.probe(
                "http://192.168.1.10/onvif/device_service", "admin", "admin123"
            )

        assert result.reachable is True
        assert result.manufacturer == "Hikvision"
        assert result.model == "DS-2CD2143G2-I"
        assert result.rtsp_url == "rtsp://192.168.1.10:554/Streaming/Channels/1"
        assert result.snapshot_url == "http://192.168.1.10/Streaming/Channels/1/picture"
        assert result.error is None

    async def test_probe_unreachable(self):
        """Probe retorna reachable=False quando câmera não responde."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("vms.cameras.onvif_client.httpx.AsyncClient", return_value=mock_client):
            result = await OnvifClient.probe(
                "http://10.0.0.1/onvif/device_service", "admin", "admin123"
            )

        assert result.reachable is False
        assert "inacessível" in (result.error or "")

    async def test_probe_timeout(self):
        """Probe retorna reachable=False em timeout."""
        import httpx

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("vms.cameras.onvif_client.httpx.AsyncClient", return_value=mock_client):
            result = await OnvifClient.probe(
                "http://192.168.1.99/onvif/device_service", "admin", "pass"
            )

        assert result.reachable is False
        assert "Timeout" in (result.error or "")

    async def test_probe_no_profiles(self):
        """Probe com profiles vazios retorna erro descritivo."""
        empty_profiles = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
  <s:Body>
    <trt:GetProfilesResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>
  </s:Body>
</s:Envelope>"""

        responses = [
            _mock_response(DEVICE_INFO_RESPONSE),
            _mock_response(empty_profiles),
        ]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=responses)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("vms.cameras.onvif_client.httpx.AsyncClient", return_value=mock_client):
            result = await OnvifClient.probe(
                "http://192.168.1.10/onvif/device_service", "admin", "pass"
            )

        assert result.reachable is True
        assert result.error is not None

    async def test_probe_without_auth(self):
        """Probe sem credenciais (câmera pública) não injeta WS-Security."""
        responses = [
            _mock_response(DEVICE_INFO_RESPONSE),
            _mock_response(PROFILES_RESPONSE),
            _mock_response(STREAM_URI_RESPONSE),
            _mock_response(SNAPSHOT_URI_RESPONSE),
        ]

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=responses)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("vms.cameras.onvif_client.httpx.AsyncClient", return_value=mock_client):
            result = await OnvifClient.probe(
                "http://192.168.1.10/onvif/device_service", "", ""
            )

        assert result.reachable is True
        # Verifica que não enviou UsernameToken (sem auth)
        call_args = mock_client.post.call_args_list[0]
        body = call_args[1].get("content") or call_args[0][1] if len(call_args[0]) > 1 else ""
        assert "UsernameToken" not in (body if isinstance(body, str) else body.decode())
