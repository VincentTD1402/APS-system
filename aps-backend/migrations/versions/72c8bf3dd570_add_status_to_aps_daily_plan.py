"""add status to aps_daily_plan

Revision ID: 72c8bf3dd570
Revises: 8076b2c791e5
Create Date: 2026-07-17 12:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "72c8bf3dd570"
down_revision: Union[str, Sequence[str], None] = "8076b2c791e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_daily_plan",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="normal"),
        schema="aps_result",
    )
    op.create_check_constraint(
        "ck_daily_plan_status",
        "aps_daily_plan",
        "status IN ('normal','overload')",
        schema="aps_result",
    )


def downgrade() -> None:
    op.drop_constraint("ck_daily_plan_status", "aps_daily_plan", schema="aps_result", type_="check")
    op.drop_column("aps_daily_plan", "status", schema="aps_result")
