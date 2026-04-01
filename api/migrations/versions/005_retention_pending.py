"""005_retention_pending — retenção pendente para upgrade de plano

Revision ID: 005
Revises: 004
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("retention_days_pending", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column("retention_pending_from", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cameras", "retention_pending_from")
    op.drop_column("cameras", "retention_days_pending")
