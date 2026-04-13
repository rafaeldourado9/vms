"""billing: license_keys + usage_records + pricing_rules (pay-per-use model)

Revision ID: 021
Revises: 020
Create Date: 2026-04-13 20:00:00.000000

Modelo de negócio:
- Licença anual: pagamento único, valida por 1 ano
- Storage: cobrança mensal por GB usado
- Analytics: pay-per-use por câmera que usa cada plugin
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '021'
down_revision: Union[str, None] = '020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. license_keys — licença anual de ativação
    op.create_table(
        'license_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('license_key', sa.String(24), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column('max_cameras', sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column('price_annual', sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint('license_key', name='uq_license_keys_key'),
        sa.Index('ix_license_keys_tenant', 'tenant_id'),
    )

    # 2. usage_records — storage mensal + analytics pay-per-use
    op.create_table(
        'usage_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('usage_type', sa.String(30), nullable=False),
        sa.Column('camera_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity', sa.Numeric(15, 4), nullable=False),
        sa.Column('unit_price', sa.Numeric(10, 4), nullable=False, server_default=sa.text("0")),
        sa.Column('total_price', sa.Numeric(15, 4), nullable=False, server_default=sa.text("0")),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Index('ix_usage_records_tenant_period', 'tenant_id', 'period_start'),
        sa.Index('ix_usage_records_type', 'usage_type'),
    )

    # 3. pricing_rules — tabela de preços editável
    op.create_table(
        'pricing_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('usage_type', sa.String(30), nullable=False),
        sa.Column('unit', sa.String(20), nullable=False, server_default=sa.text("'GB'")),
        sa.Column('price_per_unit', sa.Numeric(10, 4), nullable=False, server_default=sa.text("0")),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint('usage_type', name='uq_pricing_rules_type'),
    )

    # 4. tenant: onboarding_complete + license_key_id
    op.add_column('tenants', sa.Column('onboarding_complete', sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column('tenants', sa.Column('license_key_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'license_key_id')
    op.drop_column('tenants', 'onboarding_complete')
    op.drop_table('pricing_rules')
    op.drop_table('usage_records')
    op.drop_table('license_keys')
