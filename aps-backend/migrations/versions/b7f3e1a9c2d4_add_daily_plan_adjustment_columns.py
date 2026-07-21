"""add daily_plan adjustment columns

Revision ID: b7f3e1a9c2d4
Revises: b2c3d4e5f6a7
Create Date: 2026-07-21 00:00:00

POST /aps/adjust needs to persist manual drag/drop overrides on aps_daily_plan
that survive the next G-System-driven rebuild_daily_plan wipe-and-rebuild.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f3e1a9c2d4"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_daily_plan",
        sa.Column("adjusted", sa.Boolean(), nullable=False, server_default="false"),
        schema="aps_result",
    )
    op.add_column(
        "aps_daily_plan",
        sa.Column("original_work_date", sa.Date(), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "aps_daily_plan",
        sa.Column("original_planned_qty", sa.Numeric(14, 2), nullable=True),
        schema="aps_result",
    )


def downgrade() -> None:
    op.drop_column("aps_daily_plan", "original_planned_qty", schema="aps_result")
    op.drop_column("aps_daily_plan", "original_work_date", schema="aps_result")
    op.drop_column("aps_daily_plan", "adjusted", schema="aps_result")
