"""add gsystem bom fields

Revision ID: 8076b2c791e5
Revises: f0e82fefa4d5
Create Date: 2026-07-17 09:42:58.534759

Additive migration: adds the full G-System BOM informational field set to
`aps_input.aps_bom` (19 new nullable columns). Table already exists in
merged form — this is ADD COLUMN only, no data loss.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8076b2c791e5'
down_revision: Union[str, Sequence[str], None] = 'f0e82fefa4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('aps_bom', sa.Column('gsystem_if_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('gsystem_bom_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('parent_item_no', sa.String(length=50), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('component_item_no', sa.String(length=50), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('bom_level', sa.String(length=10), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('start_date', sa.String(length=8), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('end_date', sa.String(length=8), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('delivery_type', sa.String(length=50), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('delivery_type_name', sa.String(length=100), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('rev_no', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('if_recv_yn', sa.Boolean(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('if_recv_dt', sa.DateTime(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('reg_dt', sa.DateTime(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('reg_user_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('mod_dt', sa.DateTime(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('mod_user_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('corp_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('biz_id', sa.Integer(), nullable=True), schema='aps_input')
    op.add_column('aps_bom', sa.Column('if_status', sa.String(length=10), nullable=True), schema='aps_input')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('aps_bom', 'if_status', schema='aps_input')
    op.drop_column('aps_bom', 'biz_id', schema='aps_input')
    op.drop_column('aps_bom', 'corp_id', schema='aps_input')
    op.drop_column('aps_bom', 'mod_user_id', schema='aps_input')
    op.drop_column('aps_bom', 'mod_dt', schema='aps_input')
    op.drop_column('aps_bom', 'reg_user_id', schema='aps_input')
    op.drop_column('aps_bom', 'reg_dt', schema='aps_input')
    op.drop_column('aps_bom', 'if_recv_dt', schema='aps_input')
    op.drop_column('aps_bom', 'if_recv_yn', schema='aps_input')
    op.drop_column('aps_bom', 'rev_no', schema='aps_input')
    op.drop_column('aps_bom', 'delivery_type_name', schema='aps_input')
    op.drop_column('aps_bom', 'delivery_type', schema='aps_input')
    op.drop_column('aps_bom', 'end_date', schema='aps_input')
    op.drop_column('aps_bom', 'start_date', schema='aps_input')
    op.drop_column('aps_bom', 'bom_level', schema='aps_input')
    op.drop_column('aps_bom', 'component_item_no', schema='aps_input')
    op.drop_column('aps_bom', 'parent_item_no', schema='aps_input')
    op.drop_column('aps_bom', 'gsystem_bom_id', schema='aps_input')
    op.drop_column('aps_bom', 'gsystem_if_id', schema='aps_input')
