"""005_remove_roi_table — remove tabela de ROIs (responsabilidade migrada para plugins)

Revision ID: 005
Revises: 004
Create Date: 2026-04-10
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: str = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.drop_table("regions_of_interest")


def downgrade() -> None:
    op.create_table(
        "regions_of_interest",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "camera_id",
            sa.String(36),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ia_type", sa.String(100), nullable=False),
        sa.Column("polygon_points", sa.JSON(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_roi_tenant_id", "regions_of_interest", ["tenant_id"])
    op.create_index("ix_roi_camera_id", "regions_of_interest", ["camera_id"])
