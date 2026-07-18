"""create aps_material_shortage table

Revision ID: b2f5a9c1e4d7
Revises: c2dfb08cc6a6
Create Date: 2026-07-17 19:55:00

Per-component required-vs-available rollup for material shortage (자재부족),
computed on demand from aps_mps_plan × aps_bom vs aps_stock.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2f5a9c1e4d7"
down_revision: Union[str, Sequence[str], None] = "c2dfb08cc6a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aps_material_shortage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("item_no", sa.String(length=50), nullable=True),
        sa.Column("item_name", sa.String(length=200), nullable=True),
        sa.Column("required_qty", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("available_qty", sa.Numeric(precision=18, scale=4), server_default="0", nullable=False),
        sa.Column("shortage_qty", sa.Numeric(precision=18, scale=4), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["aps_input.aps_item.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="aps_result",
    )
    op.create_index("ix_aps_material_shortage_item_id", "aps_material_shortage", ["item_id"], schema="aps_result")
    op.create_index("ix_aps_material_shortage_shortage_qty", "aps_material_shortage", ["shortage_qty"], schema="aps_result")


def downgrade() -> None:
    op.drop_index("ix_aps_material_shortage_shortage_qty", table_name="aps_material_shortage", schema="aps_result")
    op.drop_index("ix_aps_material_shortage_item_id", table_name="aps_material_shortage", schema="aps_result")
    op.drop_table("aps_material_shortage", schema="aps_result")
