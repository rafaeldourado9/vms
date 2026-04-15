"""Cliente HTTP para a API v3 do MediaMTX."""
from __future__ import annotations

import logging

import httpx

from vms.infrastructure.config import get_settings

logger = logging.getLogger(__name__)


class MediaMTXClient:
    """Cliente assíncrono para gerenciar paths no MediaMTX."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or get_settings().mediamtx_api_url

    async def health_check(self) -> bool:
        """
        Verifica se a API do MediaMTX está respondendo.
        Retorna True se saudável, False caso contrário.
        """
        # Tenta acessar a API de controle do MediaMTX
        url = f"{self._base_url}/v3/config/global/get"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("Health check MediaMTX OK via %s", self._base_url)
                    return True
                else:
                    logger.warning("Health check MediaMTX status: %d via %s", response.status_code, self._base_url)
                    return False
        except httpx.ConnectError as exc:
            logger.warning("Health check MediaMTX falhou (connect): %s - %s", self._base_url, exc)
            return False
        except Exception as exc:
            logger.warning("Health check MediaMTX falhou (%s): %s - %s", type(exc).__name__, self._base_url, exc)
            return False

    async def add_path(self, path: str, source_url: str = "") -> bool:
        """
        Adiciona path de stream no MediaMTX. Retorna True se OK.

        - source_url vazio: MediaMTX aceita qualquer publisher (RTMP push / câmeras ativas)
        - source_url preenchido: MediaMTX faz pull do RTSP (modo agent)
        
        Se o path já existe, faz update em vez de create.
        """
        url = f"{self._base_url}/v3/config/paths/add/{path}"
        body: dict = {"name": path, "record": True}
        if source_url:
            body["source"] = source_url
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=body)
                
                # 200 OK = path criado
                if response.status_code == 200:
                    logger.debug("Path MediaMTX adicionado: %s", path)
                    return True
                
                # 400 = path já existe, tenta update
                if response.status_code == 400:
                    logger.debug("Path já existe, tentando update: %s", path)
                    return await self._update_path(path, source_url)
                
                logger.warning(
                    "Erro HTTP ao adicionar path '%s' no MediaMTX: %s - %s",
                    path,
                    response.status_code,
                    response.text,
                )
                return False
        except Exception as exc:
            logger.warning("Falha ao adicionar path '%s' no MediaMTX: %s", path, exc)
            return False

    async def _update_path(self, path: str, source_url: str = "") -> bool:
        """Atualiza path existente no MediaMTX. Se não existe, cria."""
        url = f"{self._base_url}/v3/config/paths/edit/{path}"
        body: dict = {"name": path}
        if source_url:
            body["source"] = source_url
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=body)
                
                if response.status_code == 200:
                    logger.debug("Path MediaMTX atualizado: %s", path)
                    return True
                
                # 404 = path não existe, tenta criar
                if response.status_code == 404:
                    logger.debug("Path não existe, tentando criar: %s", path)
                    return await self._create_path(path, source_url)
                
                logger.warning(
                    "Erro HTTP ao atualizar path '%s' no MediaMTX: %s",
                    path,
                    response.status_code,
                )
                return False
        except Exception as exc:
            logger.warning("Falha ao atualizar path '%s' no MediaMTX: %s", path, exc)
            return False
    
    async def _create_path(self, path: str, source_url: str = "") -> bool:
        """Cria path no MediaMTX."""
        url = f"{self._base_url}/v3/config/paths/add/{path}"
        body: dict = {"name": path, "record": True}
        if source_url:
            body["source"] = source_url
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=body)
                
                if response.status_code == 200:
                    logger.info("Path MediaMTX criado: %s", path)
                    return True
                
                # 400 = path já existe (condição de race), considera sucesso
                if response.status_code == 400:
                    logger.debug("Path já existe (race condition): %s", path)
                    return True
                
                logger.warning(
                    "Erro HTTP ao criar path '%s' no MediaMTX: %s",
                    path,
                    response.status_code,
                )
                return False
        except Exception as exc:
            logger.warning("Falha ao criar path '%s' no MediaMTX: %s", path, exc)
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
