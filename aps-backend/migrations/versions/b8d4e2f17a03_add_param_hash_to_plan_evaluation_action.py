"""add param_hash column and unique index to plan_evaluation_action

Revision ID: b8d4e2f17a03
Revises: a7c3d1f98b04
Create Date: 2026-04-30 15:30:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b8d4e2f17a03'
down_revision: Union[str, Sequence[str], None] = 'a7c3d1f98b04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'plan_evaluation_action',
        sa.Column('param_hash', sa.String(64), nullable=True),
        schema='aps_result',
    )
    op.create_index(
        'uq_action_impacted_type_hash',
        'plan_evaluation_action',
        ['impacted_id', 'action_type', 'param_hash'],
        unique=True,
        schema='aps_result',
    )


def downgrade() -> None:
    op.drop_index(
        'uq_action_impacted_type_hash',
        table_name='plan_evaluation_action',
        schema='aps_result',
    )
    op.drop_column(
        'plan_evaluation_action',
        'param_hash',
        schema='aps_result',
    )
