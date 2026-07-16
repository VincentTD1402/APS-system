"""add gsystem_sync_job table for persistent job store

Revision ID: c9f5a3b28d01
Revises: b8d4e2f17a03
Create Date: 2026-04-30 15:45:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = 'c9f5a3b28d01'
down_revision: Union[str, Sequence[str], None] = 'b8d4e2f17a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gsystem_sync_job',
        sa.Column('job_id', sa.String(36), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('counts', postgresql.JSONB(), nullable=True),
        sa.Column('calendar_synced', sa.Integer(), nullable=False, server_default='0'),
        schema='aps_result',
    )


def downgrade() -> None:
    op.drop_table('gsystem_sync_job', schema='aps_result')
