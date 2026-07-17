"""merge aps_bom + aps_bom_component into single aps_bom table, add qty2

Revision ID: f0e82fefa4d5
Revises: f3b6d81a5c92
Create Date: 2026-07-17

The `aps_bom` header table held only `id` + `parent_item_id` — verified pure
wrapper adding no value beyond what each `aps_bom_component` line already
carries via its own FK. Collapsing both into one `aps_bom` table:
  parent_item_id, component_item_id, qty1 (was `quantity`), qty2 (NEW —
  previously dropped by the G-System sync), bom_seq.

Demo/seed data only (no production-data indication) — safe to drop +
recreate; rows are re-seedable via app/scripts/seed_*.py.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f0e82fefa4d5'
down_revision = 'f3b6d81a5c92'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # aps_bom_component owns the FK into aps_bom.id — drop it first.
    op.drop_table('aps_bom_component', schema='aps_input')
    op.drop_table('aps_bom', schema='aps_input')

    op.create_table(
        'aps_bom',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parent_item_id', sa.Integer(), nullable=False),
        sa.Column('component_item_id', sa.Integer(), nullable=False),
        sa.Column('qty1', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('qty2', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('bom_seq', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['parent_item_id'], ['aps_input.aps_item.id']),
        sa.ForeignKeyConstraint(['component_item_id'], ['aps_input.aps_item.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parent_item_id', 'component_item_id', name='uq_aps_bom_parent_component'),
        schema='aps_input',
    )


def downgrade() -> None:
    op.drop_table('aps_bom', schema='aps_input')

    op.create_table(
        'aps_bom',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parent_item_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['parent_item_id'], ['aps_input.aps_item.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='aps_input',
    )
    op.create_table(
        'aps_bom_component',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bom_id', sa.Integer(), nullable=False),
        sa.Column('component_item_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column('bom_seq', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['bom_id'], ['aps_input.aps_bom.id']),
        sa.ForeignKeyConstraint(['component_item_id'], ['aps_input.aps_item.id']),
        sa.PrimaryKeyConstraint('id'),
        schema='aps_input',
    )
