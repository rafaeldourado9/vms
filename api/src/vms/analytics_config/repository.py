"""Ports (interfaces) e implementações SQLAlchemy para ROIs de analytics."""
from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.analytics_config.domain import RegionOfInterest
from vms.analytics_config.models import RegionOfInterestModel


# ─── Port (interface) ─────────────────────────────────────────────────────────

class ROIRepositoryPort(Protocol):
    """Interface do repositório de Regiões de Interesse."""

    async def list_by_camera(
        self, camera_id: str, tenant_id: str, active_only: bool = True
    ) -> list[RegionOfInterest]: ...

    async def list_by_tenant(self, tenant_id: str) -> list[RegionOfInterest]: ...

    async def get_by_id(
        self, roi_id: str, tenant_id: str
    ) -> RegionOfInterest | None: ...

    async def create(self, roi: RegionOfInterest) -> RegionOfInterest: ...

    async def update(self, roi: RegionOfInterest) -> RegionOfInterest: ...

    async def delete(self, roi_id: str, tenant_id: str) -> bool: ...


# ─── Conversor ORM ↔ Domain ───────────────────────────────────────────────────

def _to_domain(m: RegionOfInterestModel) -> RegionOfInterest:
    """Converte modelo ORM para entidade de domínio."""
    return RegionOfInterest(
        id=m.id,
        tenant_id=m.tenant_id,
        camera_id=m.camera_id,
        name=m.name,
        ia_type=m.ia_type,
        polygon_points=m.polygon_points,
        config=m.config,
        is_active=m.is_active,
        created_at=m.created_at,
    )


# ─── Implementação SQLAlchemy ─────────────────────────────────────────────────

class ROIRepository:
    """Repositório SQLAlchemy para RegionOfInterest."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_camera(
        self, camera_id: str, tenant_id: str, active_only: bool = True
    ) -> list[RegionOfInterest]:
        """Lista ROIs de uma câmera dentro do tenant."""
        stmt = select(RegionOfInterestModel).where(
            RegionOfInterestModel.camera_id == camera_id,
            RegionOfInterestModel.tenant_id == tenant_id,
        )
        if active_only:
            stmt = stmt.where(RegionOfInterestModel.is_active.is_(True))
        result = await self._session.scalars(stmt)
        return [_to_domain(m) for m in result.all()]

    async def list_by_tenant(self, tenant_id: str) -> list[RegionOfInterest]:
        """Lista todas as ROIs ativas de um tenant."""
        stmt = select(RegionOfInterestModel).where(
            RegionOfInterestModel.tenant_id == tenant_id,
            RegionOfInterestModel.is_active.is_(True),
        )
        result = await self._session.scalars(stmt)
        return [_to_domain(m) for m in result.all()]

    async def get_by_id(
        self, roi_id: str, tenant_id: str
    ) -> RegionOfInterest | None:
        """Busca ROI por ID dentro do tenant."""
        stmt = select(RegionOfInterestModel).where(
            RegionOfInterestModel.id == roi_id,
            RegionOfInterestModel.tenant_id == tenant_id,
        )
        result = await self._session.scalar(stmt)
        return _to_domain(result) if result else None

    async def create(self, roi: RegionOfInterest) -> RegionOfInterest:
        """Persiste nova ROI."""
        model = RegionOfInterestModel(
            id=roi.id or str(uuid.uuid4()),
            tenant_id=roi.tenant_id,
            camera_id=roi.camera_id,
            name=roi.name,
            ia_type=roi.ia_type,
            polygon_points=roi.polygon_points,
            config=roi.config,
            is_active=roi.is_active,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def update(self, roi: RegionOfInterest) -> RegionOfInterest:
        """Atualiza ROI existente."""
        stmt = select(RegionOfInterestModel).where(
            RegionOfInterestModel.id == roi.id,
            RegionOfInterestModel.tenant_id == roi.tenant_id,
        )
        model = await self._session.scalar(stmt)
        if not model:
            from vms.core.exceptions import NotFoundError
            raise NotFoundError("RegionOfInterest", roi.id)

        model.name = roi.name
        model.ia_type = roi.ia_type
        model.polygon_points = roi.polygon_points
        model.config = roi.config
        model.is_active = roi.is_active
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def delete(self, roi_id: str, tenant_id: str) -> bool:
        """Remove ROI. Retorna False se não encontrada."""
        stmt = select(RegionOfInterestModel).where(
            RegionOfInterestModel.id == roi_id,
            RegionOfInterestModel.tenant_id == tenant_id,
        )
        model = await self._session.scalar(stmt)
        if not model:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True
