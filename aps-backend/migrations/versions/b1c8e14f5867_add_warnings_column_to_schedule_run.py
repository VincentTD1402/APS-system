"""add warnings column to schedule_run

Revision ID: b1c8e14f5867
Revises: e2f7b5c49d03
Create Date: 2026-05-04 07:38:22.592480

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c8e14f5867'
down_revision: Union[str, Sequence[str], None] = 'e2f7b5c49d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("aps_schedule_run", sa.Column("warnings", sa.Text(), nullable=True), schema="aps_input")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("aps_schedule_run", "warnings", schema="aps_input")
