"""Testes unitários do ISAPIClient — Hikvision ISAPI HTTP client."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from vms.infrastructure.cameras.isapi_client import ISAPIClient


class TestISAPIClientInit:
    """Testes de inicialização do ISAPIClient."""

    def test_init_strips_base_url(self):
        """Base URL é stripped de trailing slash."""
        client = ISAPIClient("http://192.168.1.64/ISAPI/", "admin", "senha")
        assert client._base_url == "http://192.168.1.64/ISAPI"

    def test_init_defaults(self):
        """Defaults de timeout, retry_count, retry_delay."""
        client = ISAPIClient("http://192.168.1.64/ISAPI", "admin", "senha")
        assert client._timeout == 10.0
        assert client._retry_count == 3
        assert client._retry_delay == 2.0

    def test_init_custom_values(self):
        """Valores customizados são aceitos."""
        client = ISAPIClient(
            "http://192.168.1.64/ISAPI",
            "admin",
            "senha",
            timeout=5.0,
            retry_count=5,
            retry_delay=1.0,
        )
        assert client._timeout == 5.0
        assert client._retry_count == 5
        assert client._retry_delay == 1.0


class TestISAPIRequest:
    """Testes do método _request com retry."""

    @pytest.fixture
    def client(self):
        return ISAPIClient(
            "http://192.168.1.64/ISAPI",
            "admin",
            "senha",
            retry_count=3,
            retry_delay=0.01,  # rápido para testes
        )

    async def test_request_success(self, client):
        """GET com sucesso retorna response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.text = "<DeviceName>Test</DeviceName>"

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            response = await client._request("GET", "System/deviceInfo")
            assert response.status_code == 200

    async def test_request_retry_on_failure_then_success(self, client):
        """Retry após falha, sucesso na segunda tentativa."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/xml"}
        mock_response.text = "<ok/>"

        call_count = 0

        async def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("connection refused")
            return mock_response

        mock_client = AsyncMock()
        mock_client.request = failing_then_success
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            response = await client._request("GET", "System/deviceInfo")
            assert call_count == 2
            assert response.status_code == 200

    async def test_request_raises_after_all_retries(self, client):
        """Após todas as retries, levanta exceção."""
        async def always_fail(*args, **kwargs):
            raise httpx.ConnectError("connection refused")

        mock_client = AsyncMock()
        mock_client.request = always_fail
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            with pytest.raises(httpx.ConnectError):
                await client._request("GET", "System/deviceInfo")


class TestISAPIGet:
    """Testes do método get (XML e JSON parsing)."""

    @pytest.fixture
    def client(self):
        c = ISAPIClient(
            "http://192.168.1.64/ISAPI",
            "admin",
            "senha",
            retry_count=1,
            retry_delay=0.01,
        )
        return c

    async def test_get_parses_xml(self, client):
        """GET com XML retorna dict parseado."""
        xml_text = """<DeviceDescription>
  <DeviceName>Hikvision Camera</DeviceName>
  <serialNumber>DS-2CD2143G2-I</serialNumber>
  <firmwareVersion>V5.7.0</firmwareVersion>
</DeviceDescription>"""

        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.text = xml_text
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # xmltodict pode não estar disponível no ambiente de testes
        import importlib
        has_xmltodict = importlib.util.find_spec("xmltodict") is not None

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.get("System/deviceInfo")
            if has_xmltodict:
                assert isinstance(result, dict)
                assert result["DeviceDescription"]["DeviceName"] == "Hikvision Camera"
            else:
                # Sem xmltodict, retorna texto puro
                assert isinstance(result, str)

    async def test_get_returns_text_on_xml_parse_failure(self, client):
        """GET com XML inválido retorna texto puro."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.text = "<invalid xml"
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.get("System/deviceInfo")
            assert result == "<invalid xml"

    async def test_get_parses_json(self, client):
        """GET com JSON retorna dict."""
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.get("System/deviceInfo")
            assert result == {"key": "value"}


class TestISAPIPut:
    """Testes do método put."""

    @pytest.fixture
    def client(self):
        return ISAPIClient(
            "http://192.168.1.64/ISAPI",
            "admin",
            "senha",
            retry_count=1,
            retry_delay=0.01,
        )

    async def test_put_returns_true(self, client):
        """PUT retorna True em caso de sucesso."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.put("Event/notification/httpHosts", data="<xml/>")
            assert result is True

    async def test_put_sends_correct_content_type(self, client):
        """PUT envia Content-Type correto."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            await client.put(
                "Event/notification/httpHosts",
                data="<xml/>",
                content_type="application/xml",
            )
            call_args = mock_client.request.call_args
            assert call_args.kwargs["headers"]["Content-Type"] == "application/xml"


class TestISAPIHighLevelMethods:
    """Testes dos métodos de alto nível."""

    @pytest.fixture
    def client(self):
        c = ISAPIClient(
            "http://192.168.1.64/ISAPI",
            "admin",
            "senha",
            retry_count=1,
            retry_delay=0.01,
        )
        return c

    async def test_get_capabilities(self, client):
        """get_capabilities retorna dict de capacidades."""
        with patch.object(client, "get", return_value={"Smart": {"VCA": True}}) as mock_get:
            result = await client.get_capabilities()
            mock_get.assert_called_once_with("System/capabilities")
            assert result == {"Smart": {"VCA": True}}

    async def test_get_capabilities_returns_empty_on_error(self, client):
        """get_capabilities retorna {} em caso de erro."""
        with patch.object(client, "get", side_effect=Exception("fail")):
            result = await client.get_capabilities()
            assert result == {}

    async def test_get_device_info(self, client):
        """get_device_info retorna info do dispositivo."""
        info = {
            "DeviceDescription": {
                "DeviceName": "DS-2CD2143G2-I",
                "serialNumber": "ABC123",
                "firmwareVersion": "V5.7.0",
            }
        }
        with patch.object(client, "get", return_value=info) as mock_get:
            result = await client.get_device_info()
            mock_get.assert_called_once_with("System/deviceInfo")
            assert result == info

    async def test_configure_alarm_server(self, client):
        """configure_alarm_server envia XML correto."""
        with patch.object(client, "put", return_value=True) as mock_put:
            result = await client.configure_alarm_server("http://vms.example.com/webhook")
            assert result is True
            mock_put.assert_called_once()
            # Verificar que o XML contém a URL
            call_data = mock_put.call_args.kwargs.get("data", "")
            assert "http://vms.example.com/webhook" in call_data
            assert "HttpHostNotificationList" in call_data

    async def test_configure_alarm_server_returns_false_on_error(self, client):
        """configure_alarm_server retorna False em caso de erro."""
        with patch.object(client, "put", side_effect=Exception("fail")):
            result = await client.configure_alarm_server("http://vms.example.com/webhook")
            assert result is False

    async def test_sync_time(self, client):
        """sync_time envia XML de tempo correto."""
        with patch.object(client, "put", return_value=True) as mock_put:
            result = await client.sync_time()
            assert result is True
            call_data = mock_put.call_args.kwargs.get("data", "")
            assert "<Time>" in call_data
            assert "<year>" in call_data

    async def test_sync_time_returns_false_on_error(self, client):
        """sync_time retorna False em caso de erro."""
        with patch.object(client, "put", side_effect=Exception("fail")):
            result = await client.sync_time()
            assert result is False

    async def test_get_snapshot(self, client):
        """get_snapshot retorna bytes da imagem."""
        image_bytes = b"\xff\xd8\xff\xe0..."  # JPEG header
        mock_response = MagicMock()
        mock_response.content = image_bytes
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_client", return_value=mock_client):
            result = await client.get_snapshot()
            assert result == image_bytes

    async def test_probe(self, client):
        """probe combina device_info + capabilities."""
        info = {
            "DeviceDescription": {
                "DeviceName": "DS-2CD2143G2-I",
                "serialNumber": "ABC123",
                "firmwareVersion": "V5.7.0",
            }
        }
        caps = {"Smart": {"VCA": True, "ANPR": True}}

        with patch.object(client, "get_device_info", return_value=info):
            with patch.object(client, "get_capabilities", return_value=caps):
                result = await client.probe()

                assert "info" in result
                assert "capabilities" in result
                assert "model_name" in result
                assert "serial_number" in result
                assert "firmware_version" in result
                assert result["capabilities"] == caps

    async def test_probe_returns_defaults_on_error(self, client):
        """probe retorna defaults se ambos falham."""
        with patch.object(client, "get_device_info", return_value={}):
            with patch.object(client, "get_capabilities", return_value={}):
                result = await client.probe()
                assert result["model_name"] == "Unknown"
                assert result["serial_number"] == "Unknown"
                assert result["firmware_version"] == "Unknown"
