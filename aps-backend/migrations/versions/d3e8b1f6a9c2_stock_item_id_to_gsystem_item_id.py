"""rename aps_stock.item_id → gsystem_item_id

Revision ID: d3e8b1f6a9c2
Revises: b2f5a9c1e4d7
Create Date: 2026-07-18 09:15:00

The column holds the G-System business item id (itemId); renamed to
gsystem_item_id for consistency with aps_mps_plan.gsystem_item_id. It still
joins aps_item.gsystem_id.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d3e8b1f6a9c2"
down_revision: Union[str, Sequence[str], None] = "b2f5a9c1e4d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "aps_stock", "item_id", new_column_name="gsystem_item_id", schema="aps_input"
    )


def downgrade() -> None:
    op.alter_column(
        "aps_stock", "gsystem_item_id", new_column_name="item_id", schema="aps_input"
    )
