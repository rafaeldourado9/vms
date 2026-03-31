"""Casos de uso do bounded context de streaming."""
from __future__ import annotations

import logging
import re
import uuid

from vms.streaming.domain import StreamSession
from vms.streaming.repository import StreamSessionRepositoryPort

logger = logging.getLogger(__name__)

_PATH_RE = re.compile(r"tenant-(?P<tenant_id>[^/]+)/cam-(?P<camera_id>.+)")


class StreamingService:
    """Casos de uso de gerenciamento de sessões de streaming."""

    def __init__(self, repo: StreamSessionRepositoryPort) -> None:
        self._repo = repo

    async def on_stream_ready(self, mediamtx_path: str) -> StreamSession | None:
        """
        Registra início de sessão quando stream fica pronto.

        Extrai tenant_id e camera_id do path MediaMTX.
        Retorna None se path inválido.
        """
        ids = _parse_path(mediamtx_path)
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

        Retorna sessão encerrada ou None se não havia sessão ativa.
        """
        ended = await self._repo.end_session(mediamtx_path)
        if ended:
            logger.info("Sessão streaming encerrada: %s", ended.id)
        else:
            logger.warning("Nenhuma sessão ativa para path: %s", mediamtx_path)
        return ended

    async def verify_publish_token(
        self, path: str, token: str
    ) -> bool:
        """
        Verifica se o token de publicação é válido.

        Valida que o path segue o padrão tenant-{x}/cam-{y} e o token
        corresponde a um agent autorizado.
        """
        ids = _parse_path(path)
        if not ids:
            return False

        # TODO: validar token contra API keys de agents do tenant
        # Por ora, aceita qualquer token não-vazio para paths válidos
        return bool(token)


def _parse_path(path: str) -> tuple[str, str] | None:
    """Extrai (tenant_id, camera_id) do path MediaMTX."""
    match = _PATH_RE.match(path)
    if not match:
        return None
    return match.group("tenant_id"), match.group("camera_id")
