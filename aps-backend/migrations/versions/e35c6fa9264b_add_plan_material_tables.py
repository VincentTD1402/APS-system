"""add_plan_material_tables

Revision ID: e35c6fa9264b
Revises: 3b1f9e7c4d02
Create Date: 2026-04-29 08:45:48.027968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e35c6fa9264b'
down_revision: Union[str, Sequence[str], None] = '3b1f9e7c4d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create plan_material table
    op.create_table(
        'plan_material',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('scenario_id', sa.String(50), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('item_id', sa.Integer, sa.ForeignKey('aps_input.aps_item.id'), nullable=False),
        sa.Column('allocated_qty', sa.Numeric(18, 4), server_default='0.0'),
        schema='aps_result'
    )

    # Create plan_material_override table
    op.create_table(
        'plan_material_override',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('scenario_id', sa.String(50), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('original_item_id', sa.Integer, nullable=False),
        sa.Column('substitute_item_id', sa.Integer, nullable=False),
        sa.Column('substitute_qty', sa.Numeric(18, 4)),
        sa.Column('status', sa.String(20), server_default='APPLIED'),
        schema='aps_result'
    )

    # Create purchase_request table
    op.create_table(
        'purchase_request',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('scenario_id', sa.String(50), nullable=False),
        sa.Column('item_id', sa.Integer, sa.ForeignKey('aps_input.aps_item.id'), nullable=False),
        sa.Column('shortage_qty', sa.Numeric(18, 4), nullable=False),
        sa.Column('need_date', sa.Date),
        sa.Column('source_type', sa.String(50), server_default='VENDOR'),
        sa.Column('status', sa.String(20), server_default='APPLIED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema='aps_result'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('purchase_request', schema='aps_result')
    op.drop_table('plan_material_override', schema='aps_result')
    op.drop_table('plan_material', schema='aps_result')
