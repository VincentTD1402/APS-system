"""add routing_id and work_time_hours to aps_item_process

Revision ID: 2ac934e03af2
Revises: 2169c8ce60d1
Create Date: 2026-04-29 01:07:57.124454

Changes:
  - aps_input.aps_item_process: add routing_id (FK, nullable) + work_time_hours (numeric, nullable)
  - Drop old unique constraint (item_id, proc_sno)
  - Add new unique constraint (routing_id, item_id, proc_sno) — allows same item in multiple routings
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '2ac934e03af2'
down_revision: Union[str, Sequence[str], None] = '2169c8ce60d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'aps_item_process',
        sa.Column('routing_id', sa.Integer(), nullable=True),
        schema='aps_input',
    )
    op.add_column(
        'aps_item_process',
        sa.Column('work_time_hours', sa.Numeric(precision=10, scale=4), nullable=True),
        schema='aps_input',
    )
    op.create_foreign_key(
        'fk_item_process_routing_id',
        'aps_item_process', 'aps_routing',
        ['routing_id'], ['id'],
        source_schema='aps_input', referent_schema='aps_input',
    )
    op.create_index(
        'ix_aps_input_aps_item_process_routing_id',
        'aps_item_process', ['routing_id'],
        schema='aps_input',
    )
    # Replace old unique constraint with routing-aware one
    op.drop_constraint('aps_item_process_item_id_proc_sno_key', 'aps_item_process', schema='aps_input')
    op.create_unique_constraint(
        'uq_item_process_routing_item_sno',
        'aps_item_process', ['routing_id', 'item_id', 'proc_sno'],
        schema='aps_input',
    )


def downgrade() -> None:
    op.drop_constraint('uq_item_process_routing_item_sno', 'aps_item_process', schema='aps_input')
    op.create_unique_constraint(
        'aps_item_process_item_id_proc_sno_key',
        'aps_item_process', ['item_id', 'proc_sno'],
        schema='aps_input',
    )
    op.drop_index('ix_aps_input_aps_item_process_routing_id', table_name='aps_item_process', schema='aps_input')
    op.drop_constraint('fk_item_process_routing_id', 'aps_item_process', schema='aps_input')
    op.drop_column('aps_item_process', 'work_time_hours', schema='aps_input')
    op.drop_column('aps_item_process', 'routing_id', schema='aps_input')
