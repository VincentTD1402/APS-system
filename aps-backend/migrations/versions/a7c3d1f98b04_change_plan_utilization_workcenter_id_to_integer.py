"""change plan_utilization.workcenter_id from varchar to integer

Revision ID: a7c3d1f98b04
Revises: 3b1f9e7c4d02
Create Date: 2026-04-30 14:57:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'a7c3d1f98b04'
down_revision: Union[str, Sequence[str], None] = '3b1f9e7c4d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'plan_utilization',
        'workcenter_id',
        type_=sa.Integer(),
        postgresql_using='workcenter_id::integer',
        schema='aps_result',
    )


def downgrade() -> None:
    op.alter_column(
        'plan_utilization',
        'workcenter_id',
        type_=sa.String(50),
        postgresql_using='workcenter_id::varchar',
        schema='aps_result',
    )
