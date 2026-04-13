"""Schemas Pydantic para relatórios."""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from vms.reports.domain import ReportType


class CreateReportRequest(BaseModel):
    """Solicitação de geração de relatório."""

    report_type: ReportType
    parameters: dict = Field(default_factory=dict)
    # Exemplo: {"from": "2026-01-01", "to": "2026-01-31", "camera_id": "..."}


class ReportResponse(BaseModel):
    """Resposta com dados do relatório."""

    id: str
    tenant_id: str
    report_type: str
    parameters: dict
    status: str
    file_path: str | None = None
    sha256_hash: str | None = None
    generated_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    """Lista paginada de relatórios."""

    items: list[ReportResponse]
    total: int
    page: int
    page_size: int

    @classmethod
    def build(cls, items: list, total: int, page: int, page_size: int) -> "ReportListResponse":
        return cls(
            items=[ReportResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
