"""Casos de uso do bounded context de streaming."""
from __future__ import annotations

import logging
import re
import uuid

from vms.cameras.repository import CameraRepositoryPort
from vms.iam.repository import ApiKeyRepositoryPort
from vms.streaming.domain import StreamSession
from vms.streaming.repository import StreamSessionRepositoryPort

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")
_LIVE_RE = re.compile(r"live/(?P<stream_key>[^/]+?)(?:\.stream)?$")


class StreamingService:
    """Casos de uso de gerenciamento de sessões de streaming."""

    def __init__(
        self,
        repo: StreamSessionRepositoryPort,
        camera_repo: CameraRepositoryPort | None = None,
        api_key_repo: ApiKeyRepositoryPort | None = None,
    ) -> None:
        self._repo = repo
        self._camera_repo = camera_repo
        self._api_key_repo = api_key_repo

    async def on_stream_ready(self, mediamtx_path: str) -> StreamSession | None:
        """
        Registra início de sessão quando stream fica pronto.

        Extrai tenant_id e camera_id do path MediaMTX.
        Suporta paths tenant-{tid}/cam-{cid} e live/{stream_key}.
        Retorna None se path inválido.
        """
        ids = _parse_path(mediamtx_path)

        # Tenta resolver via stream_key para paths live/{key}
        if not ids:
            live_match = _LIVE_RE.match(mediamtx_path)
            if live_match and self._camera_repo:
                stream_key = live_match.group("stream_key")
                camera = await self._camera_repo.get_by_stream_key(stream_key)
                if camera:
                    ids = (camera.tenant_id, camera.id)

        if not ids:
            logger.warning("Path inválido em on_stream_ready: %s", mediamtx_path)
            return None

        tenant_id, camera_id = ids
        session = StreamSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            mediamtx_path=mediamtx_path,
        )
        saved = await self._repo.create(session)
        logger.info(
            "Sessão streaming iniciada: %s (tenant=%s, camera=%s)",
            saved.id, tenant_id, camera_id,
        )
        return saved

    async def on_stream_stopped(self, mediamtx_path: str) -> StreamSession | None:
        """
        Encerra sessão quando stream é parado.

        Suporta paths tenant-{tid}/cam-{cid} e live/{stream_key}.
        Retorna sessão encerrada ou None se não havia sessão ativa.
        """
        ended = await self._repo.end_session(mediamtx_path)
        if ended:
            logger.info("Sessão streaming encerrada: %s", ended.id)
        else:
            logger.warning("Nenhuma sessão ativa para path: %s", mediamtx_path)
        return ended

    async def verify_publish_token(self, path: str, token: str) -> bool:
        """
        Verifica se o token de publicação é válido.

        Suporta dois formatos de path:
        - tenant-{tid}/cam-{cid} → valida stream_key ou API key do agent
        - live/{stream_key}[.stream] → lookup pelo stream_key na câmera
        """
        if not token and not path:
            return False

        # Formato RTMP push: live/{stream_key} ou live/{stream_key}.stream
        live_match = _LIVE_RE.match(path)
        if live_match:
            stream_key = live_match.group("stream_key")
            if self._camera_repo:
                camera = await self._camera_repo.get_by_stream_key(stream_key)
                if camera and camera.rtmp_stream_key == stream_key:
                    return True
            return False

        # Formato legacy: tenant-{tid}/cam-{cid}
        ids = _parse_path(path)
        if not ids:
            return False

        tenant_id, camera_id = ids

        # Tenta validar como stream key de câmera RTMP push
        if self._camera_repo:
            camera = await self._camera_repo.get_by_id(camera_id, tenant_id)
            if camera and camera.rtmp_stream_key and camera.rtmp_stream_key == token:
                return True

        # Tenta validar como API key de agent
        if self._api_key_repo:
            from vms.core.security import extract_key_prefix, verify_api_key

            prefix = extract_key_prefix(token)
            api_key = await self._api_key_repo.get_by_prefix(prefix)
            if (
                api_key
                and api_key.is_active
                and api_key.tenant_id == tenant_id
                and verify_api_key(token, api_key.key_hash)
            ):
                await self._api_key_repo.update_last_used(api_key.id)
                return True

        return False

    async def verify_viewer_token(self, token: str, path: str) -> bool:
        """
        Verifica se o token de viewer é válido para o path dado.

        Valida JWT de tipo 'viewer' e confere se o camera_id do token
        corresponde ao path do MediaMTX (suporta tenant-path e live-path).
        """
        if not token:
            return False
        try:
            from vms.core.security import decode_token

            payload = decode_token(token)
            if payload.get("type") != "viewer":
                return False

            ids = _parse_path(path)

            # Para live/{stream_key}, resolve camera_id pelo stream_key
            if not ids:
                live_match = _LIVE_RE.match(path)
                if live_match and self._camera_repo:
                    stream_key = live_match.group("stream_key")
                    camera = await self._camera_repo.get_by_stream_key(stream_key)
                    if camera:
                        ids = (camera.tenant_id, camera.id)

            if not ids:
                return False

            _tenant_id, camera_id = ids
            return payload.get("camera_id") == camera_id
        except Exception:
            return False


def _parse_path(path: str) -> tuple[str, str] | None:
    """
    Extrai (tenant_id, camera_id) do path MediaMTX.

    Suporta formatos:
    - tenant-{tid}/cam-{cid}
    - live/{stream_key}[.stream] → retorna None (stream_key path é tratado separadamente)
    """
    match = _PATH_RE.match(path)
    if not match:
        return None
    return match.group("tenant_id"), match.group("camera_id")
