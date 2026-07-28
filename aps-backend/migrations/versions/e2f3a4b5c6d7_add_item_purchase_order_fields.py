"""add item purchase order fields

Revision ID: e2f3a4b5c6d7
Revises: d8e9f0a1b2c3
Create Date: 2026-07-28 00:10:00

G-System cm_item's assetTypeCd, lotYn, material, purchasePriceVatYn — needed
verbatim (not the normalized asset_type string) to build puOrderReq.detail
rows for purchase-request creation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aps_item",
        sa.Column("asset_type_cd", sa.String(length=20), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item",
        sa.Column("lot_yn", sa.Boolean(), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item",
        sa.Column("material", sa.String(length=200), nullable=True),
        schema="aps_input",
    )
    op.add_column(
        "aps_item",
        sa.Column("purchase_price_vat_yn", sa.Boolean(), nullable=True),
        schema="aps_input",
    )


def downgrade() -> None:
    op.drop_column("aps_item", "purchase_price_vat_yn", schema="aps_input")
    op.drop_column("aps_item", "material", schema="aps_input")
    op.drop_column("aps_item", "lot_yn", schema="aps_input")
    op.drop_column("aps_item", "asset_type_cd", schema="aps_input")
