"""Rotas HTTP de auditoria."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from vms.audit.repository import AuditRepository
from vms.audit.service import AuditService
from vms.shared.api.dependencies import CurrentUser, DbSession

router = APIRouter(prefix="/audit", tags=["audit"])


def _audit_svc(db: DbSession) -> AuditService:
    return AuditService(AuditRepository(db))


@router.get(
    "/logs",
    summary="Listar logs de auditoria",
)
async def list_audit_logs(
    claims: CurrentUser,
    db: DbSession,
    action: str | None = Query(default=None, description="Filtro por ação (ex: camera.created)"),
    user_id: str | None = Query(default=None, description="Filtro por usuário"),
    resource_type: str | None = Query(default=None, description="Filtro por tipo de recurso"),
    from_date: datetime | None = Query(default=None, alias="from"),
    to_date: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> dict:
    """
    Lista logs de auditoria do tenant com filtros.

    Acessível apenas por usuários autenticados do tenant.
    Admins podem ver todos os logs; outros roles podem ter restrições futuras.
    """
    offset = (page - 1) * page_size
    svc = _audit_svc(db)
    logs, total = await svc._repo.list_by_tenant(
        tenant_id=claims.tenant_id,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        from_date=from_date,
        to_date=to_date,
        limit=page_size,
        offset=offset,
    )

    return {
        "items": [
            {
                "id": str(log.id.value if hasattr(log.id, 'value') else log.id),
                "tenant_id": str(log.tenant_id.value if hasattr(log.tenant_id, 'value') else log.tenant_id),
                "user_id": str(log.user_id.value if hasattr(log.user_id, 'value') else log.user_id) if log.user_id else None,
                "user_email": log.user_email,
                "user_role": log.user_role,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id.value if hasattr(log.resource_id, 'value') else log.resource_id) if log.resource_id else None,
                "resource_name": log.resource_name,
                "ip_address": log.ip_address,
                "request_id": str(log.request_id) if log.request_id else None,
                "result": log.result,
                "occurred_at": log.occurred_at.isoformat(),
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
