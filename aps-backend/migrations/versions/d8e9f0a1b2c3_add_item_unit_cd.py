"""add item unit_cd

Revision ID: d8e9f0a1b2c3
Revises: b7f3e1a9c2d4
Create Date: 2026-07-28 00:00:00

G-System cm_item's unitCd (stock unit code) — needed to build the
puOrderReq stkUnitCd/stockUnitCd fields for purchase-request creation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "b7f3e1a9c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_item",
        sa.Column("unit_cd", sa.String(length=20), nullable=True),
        schema="aps_input",
    )


def downgrade() -> None:
    op.drop_column("aps_item", "unit_cd", schema="aps_input")
