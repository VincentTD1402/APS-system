"""material_shortage: add parent product/semiproduct columns (BOM-like)

Revision ID: e4a7c2d9b1f8
Revises: d3e8b1f6a9c2
Create Date: 2026-07-18 13:05:00

Row grain becomes (parent_item, component_item) — mirrors aps_bom. parent_item_id
is an FK to aps_item so the UI can link/drill like the BOM screen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4a7c2d9b1f8"
down_revision: Union[str, Sequence[str], None] = "d3e8b1f6a9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("aps_material_shortage", sa.Column("parent_item_id", sa.Integer(), nullable=True), schema="aps_result")
    op.add_column("aps_material_shortage", sa.Column("parent_item_no", sa.String(length=50), nullable=True), schema="aps_result")
    op.add_column("aps_material_shortage", sa.Column("parent_item_name", sa.String(length=200), nullable=True), schema="aps_result")
    op.create_foreign_key(
        "fk_aps_material_shortage_parent_item", "aps_material_shortage", "aps_item",
        ["parent_item_id"], ["id"],
        source_schema="aps_result", referent_schema="aps_input", ondelete="CASCADE",
    )
    op.create_index("ix_aps_material_shortage_parent_item_id", "aps_material_shortage", ["parent_item_id"], schema="aps_result")


def downgrade() -> None:
    op.drop_index("ix_aps_material_shortage_parent_item_id", table_name="aps_material_shortage", schema="aps_result")
    op.drop_constraint("fk_aps_material_shortage_parent_item", "aps_material_shortage", schema="aps_result", type_="foreignkey")
    op.drop_column("aps_material_shortage", "parent_item_name", schema="aps_result")
    op.drop_column("aps_material_shortage", "parent_item_no", schema="aps_result")
    op.drop_column("aps_material_shortage", "parent_item_id", schema="aps_result")
