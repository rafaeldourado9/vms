"""Cliente ONVIF PTZ assíncrono via SOAP raw (httpx).

Segue o mesmo padrão de cameras/onvif_client.py: sem dependência de zeep,
usando envelopes SOAP construídos manualmente para manter o container leve.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

import httpx

from vms.ptz.domain import PtzCapabilities, PtzPreset, PtzVector

_PTZ_NS = "http://www.onvif.org/ver20/ptz/wsdl"
_MEDIA_NS = "http://www.onvif.org/ver10/media/wsdl"


# ─── Templates SOAP ───────────────────────────────────────────────────────────

_GET_PROFILES_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
  <s:Body>
    <trt:GetProfiles/>
  </s:Body>
</s:Envelope>"""

_GET_CONFIGURATIONS_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body>
    <tptz:GetConfigurations/>
  </s:Body>
</s:Envelope>"""

_CONTINUOUS_MOVE_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:ContinuousMove>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
      <tptz:Velocity>
        <tt:PanTilt x="{pan}" y="{tilt}"/>
        <tt:Zoom x="{zoom}"/>
      </tptz:Velocity>
      <tptz:Timeout>PT{timeout}S</tptz:Timeout>
    </tptz:ContinuousMove>
  </s:Body>
</s:Envelope>"""

_ABSOLUTE_MOVE_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:AbsoluteMove>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
      <tptz:Position>
        <tt:PanTilt x="{pan}" y="{tilt}"/>
        <tt:Zoom x="{zoom}"/>
      </tptz:Position>
      <tptz:Speed>
        <tt:PanTilt x="{pan_speed}" y="{tilt_speed}"/>
        <tt:Zoom x="{zoom_speed}"/>
      </tptz:Speed>
    </tptz:AbsoluteMove>
  </s:Body>
</s:Envelope>"""

_STOP_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body>
    <tptz:Stop>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
      <tptz:PanTilt>true</tptz:PanTilt>
      <tptz:Zoom>true</tptz:Zoom>
    </tptz:Stop>
  </s:Body>
</s:Envelope>"""

_GET_PRESETS_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body>
    <tptz:GetPresets>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
    </tptz:GetPresets>
  </s:Body>
</s:Envelope>"""

_GOTO_PRESET_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl"
            xmlns:tt="http://www.onvif.org/ver10/schema">
  <s:Body>
    <tptz:GotoPreset>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
      <tptz:PresetToken>{preset_token}</tptz:PresetToken>
      <tptz:Speed>
        <tt:PanTilt x="0.5" y="0.5"/>
        <tt:Zoom x="0.5"/>
      </tptz:Speed>
    </tptz:GotoPreset>
  </s:Body>
</s:Envelope>"""

_SET_PRESET_BODY = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
            xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl">
  <s:Body>
    <tptz:SetPreset>
      <tptz:ProfileToken>{profile_token}</tptz:ProfileToken>
      <tptz:PresetName>{preset_name}</tptz:PresetName>
      {preset_token_elem}
    </tptz:SetPreset>
  </s:Body>
</s:Envelope>"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _inject_auth(body: str, username: str, password: str) -> str:
    """Injeta WS-Security UsernameToken no envelope SOAP."""
    if not username:
        return body
    header = f"""<s:Header>
    <Security xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <UsernameToken>
        <Username>{username}</Username>
        <Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">{password}</Password>
      </UsernameToken>
    </Security>
  </s:Header>"""
    return body.replace("<s:Body>", f"{header}\n  <s:Body>", 1)


def _local(tag: str) -> str:
    """Extrai nome local (sem namespace) de um tag XML."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_attr(root: ET.Element, local_name: str, attr: str) -> str | None:
    """Busca primeiro elemento pelo nome local e retorna um atributo."""
    for elem in root.iter():
        if _local(elem.tag) == local_name:
            val = elem.get(attr)
            if val:
                return val
    return None


def _find_text(root: ET.Element, *local_names: str) -> str | None:
    """Busca texto do primeiro elemento que combine com qualquer um dos nomes locais."""
    for elem in root.iter():
        if _local(elem.tag) in local_names and elem.text:
            return elem.text.strip()
    return None


def _ptz_url(onvif_url: str) -> str:
    """Deriva URL do serviço PTZ a partir da URL do device service."""
    return onvif_url.replace("device_service", "PTZ").replace("Device", "PTZ")


def _media_url(onvif_url: str) -> str:
    """Deriva URL do serviço Media a partir da URL do device service."""
    return onvif_url.replace("device_service", "Media")


_SOAP_HEADERS = {"Content-Type": "application/soap+xml; charset=utf-8"}


# ─── Cliente PTZ ──────────────────────────────────────────────────────────────

class PtzClient:
    """Cliente ONVIF PTZ assíncrono — usa SOAP raw via httpx."""

    @staticmethod
    async def get_profile_token(
        onvif_url: str, username: str, password: str, timeout: float = 5.0
    ) -> str | None:
        """Retorna o primeiro profile token de mídia da câmera."""
        body = _inject_auth(_GET_PROFILES_BODY, username, password)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(_media_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                if resp.status_code != 200:
                    return None
                root = ET.fromstring(resp.text)
                # token pode ser atributo do elemento Profiles/Profile
                token = _find_attr(root, "Profiles", "token") or _find_attr(root, "Profile", "token")
                return token
        except Exception:
            return None

    @staticmethod
    async def get_capabilities(
        onvif_url: str, username: str, password: str, timeout: float = 5.0
    ) -> PtzCapabilities:
        """Verifica se a câmera suporta PTZ consultando GetConfigurations."""
        ptz_url = _ptz_url(onvif_url)
        body = _inject_auth(_GET_CONFIGURATIONS_BODY, username, password)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(ptz_url, content=body, headers=_SOAP_HEADERS)
                supported = resp.status_code == 200 and "PTZConfiguration" in resp.text
                return PtzCapabilities(
                    ptz_supported=supported,
                    can_continuous_move=supported,
                    can_absolute_move=supported,
                    can_relative_move=supported,
                )
        except (httpx.ConnectError, httpx.TimeoutException):
            return PtzCapabilities(ptz_supported=False)
        except Exception:
            return PtzCapabilities(ptz_supported=False)

    @staticmethod
    async def continuous_move(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        velocity: PtzVector,
        timeout_seconds: int = 5,
        http_timeout: float = 5.0,
    ) -> bool:
        """Inicia movimento contínuo PTZ. Retorna True em sucesso."""
        body = _inject_auth(
            _CONTINUOUS_MOVE_BODY.format(
                profile_token=profile_token,
                pan=velocity.pan,
                tilt=velocity.tilt,
                zoom=velocity.zoom,
                timeout=timeout_seconds,
            ),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def absolute_move(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        position: PtzVector,
        speed: PtzVector | None = None,
        http_timeout: float = 5.0,
    ) -> bool:
        """Move para posição absoluta PTZ. Retorna True em sucesso."""
        spd = speed or PtzVector(pan=0.5, tilt=0.5, zoom=0.5)
        body = _inject_auth(
            _ABSOLUTE_MOVE_BODY.format(
                profile_token=profile_token,
                pan=position.pan,
                tilt=position.tilt,
                zoom=position.zoom,
                pan_speed=spd.pan,
                tilt_speed=spd.tilt,
                zoom_speed=spd.zoom,
            ),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def stop(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        http_timeout: float = 5.0,
    ) -> bool:
        """Para qualquer movimento PTZ em curso. Retorna True em sucesso."""
        body = _inject_auth(
            _STOP_BODY.format(profile_token=profile_token),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def get_presets(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        http_timeout: float = 5.0,
    ) -> list[PtzPreset]:
        """Retorna lista de presets PTZ salvos na câmera."""
        body = _inject_auth(
            _GET_PRESETS_BODY.format(profile_token=profile_token),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                if resp.status_code != 200:
                    return []
                root = ET.fromstring(resp.text)
                presets: list[PtzPreset] = []
                for elem in root.iter():
                    if _local(elem.tag) == "Preset":
                        token = elem.get("token", "")
                        name = _find_text(elem, "Name") or token
                        if token:
                            presets.append(PtzPreset(token=token, name=name))
                return presets
        except Exception:
            return []

    @staticmethod
    async def goto_preset(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        preset_token: str,
        http_timeout: float = 5.0,
    ) -> bool:
        """Move câmera para um preset PTZ salvo. Retorna True em sucesso."""
        body = _inject_auth(
            _GOTO_PRESET_BODY.format(
                profile_token=profile_token,
                preset_token=preset_token,
            ),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    async def set_preset(
        onvif_url: str,
        username: str,
        password: str,
        profile_token: str,
        preset_name: str,
        preset_token: str | None = None,
        http_timeout: float = 5.0,
    ) -> str | None:
        """
        Salva posição atual como preset. Se preset_token fornecido, sobrescreve.

        Retorna o token do preset criado/atualizado, ou None em falha.
        """
        token_elem = (
            f"<tptz:PresetToken>{preset_token}</tptz:PresetToken>"
            if preset_token
            else ""
        )
        body = _inject_auth(
            _SET_PRESET_BODY.format(
                profile_token=profile_token,
                preset_name=preset_name,
                preset_token_elem=token_elem,
            ),
            username,
            password,
        )
        try:
            async with httpx.AsyncClient(timeout=http_timeout) as client:
                resp = await client.post(_ptz_url(onvif_url), content=body, headers=_SOAP_HEADERS)
                if resp.status_code != 200:
                    return None
                root = ET.fromstring(resp.text)
                return _find_text(root, "PresetToken") or preset_token
        except Exception:
            return None
