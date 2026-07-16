"""Create result-level overlay tables for plan_order and plan_material.

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-03 03:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create aps_result_overlay schema if not exists
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_result_overlay;")

    # Create plan_order_overlay table
    op.create_table(
        'plan_order_overlay',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('scenario_id', sa.String(50), nullable=False, index=True),
        sa.Column('original_plan_id', sa.String(50), nullable=False, index=True),
        sa.Column('priority_score', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scenario_id', 'original_plan_id', name='uq_plan_order_overlay_scenario_plan'),
        schema='aps_result_overlay'
    )

    # Create plan_material_overlay table
    op.create_table(
        'plan_material_overlay',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('scenario_id', sa.String(50), nullable=False, index=True),
        sa.Column('original_id', sa.Integer(), nullable=False, index=True),
        sa.Column('allocated_qty', sa.Numeric(18, 4), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scenario_id', 'original_id', name='uq_plan_material_overlay_scenario_id'),
        schema='aps_result_overlay'
    )


def downgrade() -> None:
    op.drop_table('plan_material_overlay', schema='aps_result_overlay')
    op.drop_table('plan_order_overlay', schema='aps_result_overlay')
    op.execute("DROP SCHEMA IF EXISTS aps_result_overlay;")
