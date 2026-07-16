"""add work_date to operation

Revision ID: 51336be2a757
Revises: ef6118a0242f
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51336be2a757'
down_revision: str | None = 'ef6118a0242f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('aps_operation', sa.Column('work_date', sa.Date(), nullable=True), schema='aps_input')


def downgrade() -> None:
    op.drop_column('aps_operation', 'work_date', schema='aps_input')