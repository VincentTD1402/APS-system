"""simplify aps_item_routing (drop gsystem_item_id/item_rev) and add work_time/jph

Revision ID: f4b8d2a1c630
Revises: a6c2e9d4f817
Create Date: 2026-07-14 17:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4b8d2a1c630"
down_revision: Union[str, Sequence[str], None] = "a6c2e9d4f817"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_aps_item_routing_gsystem_item_id", table_name="aps_item_routing", schema="aps_input")
    op.drop_index("ix_aps_item_routing_item_rev", table_name="aps_item_routing", schema="aps_input")
    op.drop_column("aps_item_routing", "gsystem_item_id", schema="aps_input")
    op.drop_column("aps_item_routing", "item_rev", schema="aps_input")
    op.add_column(
        "aps_item_routing",
        sa.Column("work_time", sa.Numeric(precision=10, scale=2), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item_routing",
        sa.Column("jph", sa.Numeric(precision=10, scale=2), nullable=True),
        schema="aps_input",
    )


def downgrade() -> None:
    op.drop_column("aps_item_routing", "jph", schema="aps_input")
    op.drop_column("aps_item_routing", "work_time", schema="aps_input")
    op.add_column(
        "aps_item_routing",
        sa.Column("item_rev", sa.Integer(), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item_routing",
        sa.Column("gsystem_item_id", sa.Integer(), nullable=True),
        schema="aps_input",
    )
    op.create_index("ix_aps_item_routing_item_rev", "aps_item_routing", ["item_rev"], schema="aps_input")
    op.create_index("ix_aps_item_routing_gsystem_item_id", "aps_item_routing", ["gsystem_item_id"], schema="aps_input")
