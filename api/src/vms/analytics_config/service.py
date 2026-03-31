"""Application service de ROIs — casos de uso de configuração de analytics."""
from __future__ import annotations

import uuid

from vms.analytics_config.domain import RegionOfInterest
from vms.analytics_config.repository import ROIRepositoryPort
from vms.core.exceptions import NotFoundError


class ROIService:
    """Casos de uso CRUD de Regiões de Interesse."""

    def __init__(self, roi_repo: ROIRepositoryPort) -> None:
        self._rois = roi_repo

    async def create_roi(
        self,
        tenant_id: str,
        camera_id: str,
        name: str,
        ia_type: str,
        polygon_points: list[list[float]],
        config: dict,
        is_active: bool = True,
    ) -> RegionOfInterest:
        """Cria nova Região de Interesse para uma câmera do tenant."""
        roi = RegionOfInterest(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            camera_id=camera_id,
            name=name,
            ia_type=ia_type,
            polygon_points=polygon_points,
            config=config,
            is_active=is_active,
        )
        return await self._rois.create(roi)

    async def list_rois(self, tenant_id: str) -> list[RegionOfInterest]:
        """Lista todas as ROIs ativas do tenant."""
        return await self._rois.list_by_tenant(tenant_id)

    async def list_rois_by_camera(
        self, camera_id: str, tenant_id: str, active_only: bool = True
    ) -> list[RegionOfInterest]:
        """Lista ROIs de uma câmera específica."""
        return await self._rois.list_by_camera(camera_id, tenant_id, active_only)

    async def get_roi(self, roi_id: str, tenant_id: str) -> RegionOfInterest:
        """Retorna ROI por ID. Lança NotFoundError se não encontrada."""
        roi = await self._rois.get_by_id(roi_id, tenant_id)
        if not roi:
            raise NotFoundError("RegionOfInterest", roi_id)
        return roi

    async def update_roi(
        self,
        roi_id: str,
        tenant_id: str,
        name: str | None = None,
        ia_type: str | None = None,
        polygon_points: list[list[float]] | None = None,
        config: dict | None = None,
        is_active: bool | None = None,
    ) -> RegionOfInterest:
        """Aplica atualizações parciais em uma ROI existente."""
        roi = await self.get_roi(roi_id, tenant_id)
        updated = RegionOfInterest(
            id=roi.id,
            tenant_id=roi.tenant_id,
            camera_id=roi.camera_id,
            name=name if name is not None else roi.name,
            ia_type=ia_type if ia_type is not None else roi.ia_type,
            polygon_points=polygon_points if polygon_points is not None else roi.polygon_points,
            config=config if config is not None else roi.config,
            is_active=is_active if is_active is not None else roi.is_active,
            created_at=roi.created_at,
        )
        return await self._rois.update(updated)

    async def delete_roi(self, roi_id: str, tenant_id: str) -> None:
        """Remove ROI. Lança NotFoundError se não encontrada."""
        deleted = await self._rois.delete(roi_id, tenant_id)
        if not deleted:
            raise NotFoundError("RegionOfInterest", roi_id)
