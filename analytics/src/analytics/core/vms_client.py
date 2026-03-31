"""Cliente HTTP para comunicação com a VMS API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from analytics.core.config import get_settings
from analytics.core.plugin_base import ROIConfig

logger = logging.getLogger(__name__)


class VMSClient:
    """
    Cliente assíncrono para a VMS API.

    Usa analytics API key para autenticação nos endpoints internos.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.vms_api_url
        self._api_key = settings.vms_analytics_api_key
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Inicializa o cliente HTTP."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"ApiKey {self._api_key}"},
            timeout=httpx.Timeout(10.0),
        )

    async def close(self) -> None:
        """Fecha o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_camera_rois(self, camera_id: str) -> list[ROIConfig]:
        """Busca ROIs ativas de uma câmera via endpoint interno."""
        if not self._client:
            return []

        try:
            resp = await self._client.get(f"/internal/cameras/{camera_id}/rois")
            resp.raise_for_status()
            data: list[dict[str, Any]] = resp.json()
            return [
                ROIConfig(
                    id=item["id"],
                    name=item["name"],
                    ia_type=item["ia_type"],
                    polygon_points=item["polygon_points"],
                    config=item.get("config", {}),
                )
                for item in data
            ]
        except httpx.HTTPError:
            logger.exception("Erro ao buscar ROIs para câmera %s", camera_id)
            return []

    async def ingest_result(self, payload: dict) -> bool:
        """Envia resultado de analytics para o VMS API via POST /internal/analytics/ingest."""
        if not self._client:
            return False

        try:
            resp = await self._client.post("/internal/analytics/ingest", json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPError:
            logger.exception("Erro ao enviar resultado de analytics")
            return False
