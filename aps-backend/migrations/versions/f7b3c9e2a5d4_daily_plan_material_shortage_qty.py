"""daily_plan: add material_shortage_qty

Revision ID: f7b3c9e2a5d4
Revises: e4a7c2d9b1f8
Create Date: 2026-07-18 13:50:00

Per-(mps_plan, work_date) raw-material shortfall from the backward material
running balance, computed during daily-plan/rebuild.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7b3c9e2a5d4"
down_revision: Union[str, Sequence[str], None] = "e4a7c2d9b1f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_daily_plan",
        sa.Column("material_shortage_qty", sa.Numeric(precision=18, scale=4), server_default="0", nullable=False),
        schema="aps_result",
    )


def downgrade() -> None:
    op.drop_column("aps_daily_plan", "material_shortage_qty", schema="aps_result")
