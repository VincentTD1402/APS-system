"""rename work_order to aps_work_order for naming consistency

All other domain tables use the aps_ prefix (aps_item, aps_bom, aps_workcenter,
aps_mps_plan, aps_daily_plan, ...). work_order is the last odd one out — rename
for consistency. Indexes and unique constraint are renamed to match.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-21 09:15:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Indexed columns of work_order (see f9c3a7b1d2e6 redesign migration).
INDEXED_COLUMNS = [
    "temp_id",
    "mps_plan_id",
    "item_id",
    "item_routing_id",
    "workcenter_id",
    "work_order_no",
    "gsystem_work_order_id",
    "work_date",
]


def upgrade() -> None:
    op.rename_table("work_order", "aps_work_order", schema="aps_input")
    op.execute(
        'ALTER INDEX aps_input.uq_work_order_mps_plan_item_routing '
        'RENAME TO uq_aps_work_order_mps_plan_item_routing'
    )
    for col in INDEXED_COLUMNS:
        op.execute(
            f'ALTER INDEX aps_input.ix_work_order_{col} '
            f'RENAME TO ix_aps_work_order_{col}'
        )


def downgrade() -> None:
    for col in INDEXED_COLUMNS:
        op.execute(
            f'ALTER INDEX aps_input.ix_aps_work_order_{col} '
            f'RENAME TO ix_work_order_{col}'
        )
    op.execute(
        'ALTER INDEX aps_input.uq_aps_work_order_mps_plan_item_routing '
        'RENAME TO uq_work_order_mps_plan_item_routing'
    )
    op.rename_table("aps_work_order", "work_order", schema="aps_input")
