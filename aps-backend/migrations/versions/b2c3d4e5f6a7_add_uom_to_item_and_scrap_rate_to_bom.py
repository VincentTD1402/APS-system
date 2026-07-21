"""add uom to aps_item and scrap_rate to aps_bom

Master fields needed by the FE master views (Items, BOM). G-System sync does not
provide either yet, so both are nullable with sane defaults (uom='EA', scrap_rate=0)
and can be backfilled later.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-21 13:25:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'aps_item',
        sa.Column('uom', sa.String(length=20), nullable=True, server_default='EA'),
        schema='aps_input',
    )
    op.add_column(
        'aps_bom',
        sa.Column('scrap_rate', sa.Numeric(9, 4), nullable=True, server_default='0'),
        schema='aps_input',
    )


def downgrade() -> None:
    op.drop_column('aps_bom', 'scrap_rate', schema='aps_input')
    op.drop_column('aps_item', 'uom', schema='aps_input')
