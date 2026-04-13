"""Repositório SQLAlchemy para licenças."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vms.billing.domain import License, LicenseStatus, LicenseType, LicenseValidation
from vms.billing.models import LicenseModel


class LicenseRepositoryPort(Protocol):
    """Interface do repositório de licenças."""

    async def create(self, license: License) -> License: ...
    async def get_by_camera(self, camera_id: str, tenant_id: str) -> License | None: ...
    async def get_active_by_tenant(self, tenant_id: str) -> list[License]: ...
    async def validate_camera(self, camera_id: str, tenant_id: str) -> LicenseValidation: ...


def _to_domain(model: LicenseModel) -> License:
    return License(
        id=model.id,
        tenant_id=model.tenant_id,
        camera_id=model.camera_id,
        license_type=LicenseType(model.license_type),
        status=LicenseStatus(model.status),
        storage_limit_gb=model.storage_limit_gb,
        analytics_enabled=model.analytics_enabled if model.analytics_enabled is not None else False,
        activated_at=model.activated_at or datetime.utcnow(),
        expires_at=model.expires_at,
        created_at=model.created_at or datetime.utcnow(),
    )


class LicenseRepository:
    """Repositório SQLAlchemy para Licenças."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, license: License) -> License:
        """Cria nova licença."""
        model = LicenseModel(
            id=license.id if hasattr(license.id, 'value') else license.id,
            tenant_id=license.tenant_id.value if hasattr(license.tenant_id, 'value') else license.tenant_id,
            camera_id=license.camera_id,
            license_type=license.license_type,
            status=license.status,
            storage_limit_gb=license.storage_limit_gb,
            analytics_enabled=license.analytics_enabled,
            expires_at=license.expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_domain(model)

    async def get_by_camera(self, camera_id: str, tenant_id: str) -> License | None:
        """Busca licença ativa de uma câmera."""
        stmt = select(LicenseModel).where(
            LicenseModel.camera_id == camera_id,
            LicenseModel.tenant_id == tenant_id,
            LicenseModel.status == LicenseStatus.ACTIVE,
        )
        model = await self._session.scalar(stmt)
        return _to_domain(model) if model else None

    async def get_active_by_tenant(self, tenant_id: str) -> list[License]:
        """Lista licenças ativas do tenant."""
        stmt = select(LicenseModel).where(
            LicenseModel.tenant_id == tenant_id,
            LicenseModel.status == LicenseStatus.ACTIVE,
        )
        result = await self._session.scalars(stmt)
        return [_to_domain(m) for m in result.all()]

    async def validate_camera(self, camera_id: str, tenant_id: str) -> LicenseValidation:
        """Valida se câmera tem licença ativa."""
        license = await self.get_by_camera(camera_id, tenant_id)

        if not license:
            return LicenseValidation(
                is_valid=False,
                reason="Nenhuma licença encontrada para esta câmera",
            )

        if not license.is_active:
            return LicenseValidation(
                is_valid=False,
                license=license,
                reason=f"Licença {license.license_type} expirada ou inativa",
            )

        return LicenseValidation(is_valid=True, license=license)

    async def count_active_by_tenant(self, tenant_id: str) -> int:
        """Conta licenças ativas do tenant."""
        stmt = select(func.count()).select_from(LicenseModel).where(
            LicenseModel.tenant_id == tenant_id,
            LicenseModel.status == LicenseStatus.ACTIVE,
        )
        return await self._session.scalar(stmt) or 0
