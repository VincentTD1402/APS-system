"""add gsystem_id to aps_item

Revision ID: 3b1f9e7c4d02
Revises: 2ac934e03af2
Create Date: 2026-04-29 01:20:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = '3b1f9e7c4d02'
down_revision: Union[str, Sequence[str], None] = '2ac934e03af2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'aps_item',
        sa.Column('gsystem_id', sa.Integer(), nullable=True),
        schema='aps_input',
    )
    op.create_unique_constraint(
        'uq_aps_item_gsystem_id',
        'aps_item', ['gsystem_id'],
        schema='aps_input',
    )


def downgrade() -> None:
    op.drop_constraint('uq_aps_item_gsystem_id', 'aps_item', schema='aps_input')
    op.drop_column('aps_item', 'gsystem_id', schema='aps_input')
