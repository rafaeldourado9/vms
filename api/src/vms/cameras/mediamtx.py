"""Cliente HTTP para a API v3 do MediaMTX."""
from __future__ import annotations

import logging

import httpx

from vms.core.config import get_settings

logger = logging.getLogger(__name__)


class MediaMTXClient:
    """Cliente assíncrono para gerenciar paths no MediaMTX."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or get_settings().mediamtx_api_url

    async def add_path(self, path: str) -> bool:
        """Adiciona path de stream no MediaMTX. Retorna True se OK."""
        url = f"{self._base_url}/v3/config/paths/add/{path}"
        body = {"name": path, "source": "", "record": True}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=body)
                response.raise_for_status()
                logger.debug("Path MediaMTX adicionado: %s", path)
                return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Erro HTTP ao adicionar path '%s' no MediaMTX: %s",
                path,
                exc.response.status_code,
            )
            return False
        except Exception as exc:
            logger.warning("Falha ao adicionar path '%s' no MediaMTX: %s", path, exc)
            return False

    async def remove_path(self, path: str) -> bool:
        """Remove path de stream. Retorna True se OK."""
        url = f"{self._base_url}/v3/config/paths/delete/{path}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.delete(url)
                response.raise_for_status()
                logger.debug("Path MediaMTX removido: %s", path)
                return True
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Erro HTTP ao remover path '%s' do MediaMTX: %s",
                path,
                exc.response.status_code,
            )
            return False
        except Exception as exc:
            logger.warning("Falha ao remover path '%s' do MediaMTX: %s", path, exc)
            return False

    async def list_paths(self) -> list[dict]:
        """Lista todos os paths ativos."""
        url = f"{self._base_url}/v3/paths/list"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
                return data.get("items", [])
        except Exception as exc:
            logger.warning("Falha ao listar paths do MediaMTX: %s", exc)
            return []
