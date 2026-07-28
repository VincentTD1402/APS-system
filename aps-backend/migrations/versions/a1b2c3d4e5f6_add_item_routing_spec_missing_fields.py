"""add fields to item_routing_spec missed on first itemRoutingMng field scan

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-07-28 12:00:00

The prior migration (f4a5b6c7d8e9) rebuilt aps_item_routing_spec from a
sample of only ~7 items, which happened to have no routingId/inspecType/
leadTime/sampleQty on any row — wrongly concluded those fields don't exist
on this endpoint. A full scan across all 150 aps_item rows (69 routing rows)
shows they do appear on other items. Adding them back, plus routingNo/Nm/
TypeCd/GroupCd, inspecPeriod, lossRate, toolId, remark — none of these are
local FKs (aps_routing was correctly dropped as dead code separately; these
are just the raw G-System reference id/codes, stored verbatim).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f4a5b6c7d8e9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aps_item_routing_spec", sa.Column("gsystem_routing_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_no", sa.String(50), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_name", sa.String(200), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_type_cd", sa.String(20), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("routing_group_cd", sa.String(20), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("lead_time", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("inspec_type", sa.String(20), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("inspec_period", sa.String(20), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("sample_qty", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("loss_rate", sa.Numeric(10, 2), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("tool_id", sa.Integer(), nullable=True), schema="aps_input")
    op.add_column("aps_item_routing_spec", sa.Column("remark", sa.String(500), nullable=True), schema="aps_input")


def downgrade() -> None:
    op.drop_column("aps_item_routing_spec", "remark", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "tool_id", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "loss_rate", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "sample_qty", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "inspec_period", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "inspec_type", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "lead_time", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_group_cd", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_type_cd", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_name", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "routing_no", schema="aps_input")
    op.drop_column("aps_item_routing_spec", "gsystem_routing_id", schema="aps_input")
