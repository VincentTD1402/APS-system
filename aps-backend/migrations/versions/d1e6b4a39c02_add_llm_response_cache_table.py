"""add llm_response_cache table

Revision ID: d1e6b4a39c02
Revises: c9f5a3b28d01
Create Date: 2026-05-03 14:30:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'd1e6b4a39c02'
down_revision: Union[str, Sequence[str], None] = 'c9f5a3b28d01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'llm_response_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('scenario_id', sa.String(), sa.ForeignKey('aps_result.plan_scenario.scenario_id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('cache_type', sa.String(20), nullable=False),
        sa.Column('cache_key', sa.String(200), nullable=False),
        sa.Column('response_json', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema='aps_result',
    )
    op.create_index(
        'uq_llm_cache_scenario_type_key',
        'llm_response_cache',
        ['scenario_id', 'cache_type', 'cache_key'],
        unique=True,
        schema='aps_result',
    )


def downgrade() -> None:
    op.drop_index('uq_llm_cache_scenario_type_key', table_name='llm_response_cache', schema='aps_result')
    op.drop_table('llm_response_cache', schema='aps_result')
