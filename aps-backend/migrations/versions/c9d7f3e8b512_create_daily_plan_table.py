"""create aps_daily_plan table

Revision ID: c9d7f3e8b512
Revises: b7e19c5a2d43
Create Date: 2026-07-14 18:50:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d7f3e8b512"
down_revision: Union[str, Sequence[str], None] = "b7e19c5a2d43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "aps_daily_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mps_plan_id", sa.Integer(), nullable=False),
        sa.Column("item_routing_id", sa.Integer(), nullable=False),
        sa.Column("workcenter_id", sa.Integer(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("planned_qty", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["mps_plan_id"], ["aps_input.aps_mps_plan.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_routing_id"], ["aps_input.aps_item_routing.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workcenter_id"], ["aps_input.aps_workcenter.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="aps_result",
    )
    for column in ("mps_plan_id", "item_routing_id", "workcenter_id", "work_date"):
        op.create_index(f"ix_aps_daily_plan_{column}", "aps_daily_plan", [column], schema="aps_result")


def downgrade() -> None:
    for column in ("mps_plan_id", "item_routing_id", "workcenter_id", "work_date"):
        op.drop_index(f"ix_aps_daily_plan_{column}", table_name="aps_daily_plan", schema="aps_result")
    op.drop_table("aps_daily_plan", schema="aps_result")
