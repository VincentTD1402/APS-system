"""merge heads

Revision ID: ddaa67fe83f8
Revises: b1c2d3a4b5c6, e2f7b5c49d03
Create Date: 2026-05-04 06:26:55.996057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddaa67fe83f8'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3a4b5c6', 'e2f7b5c49d03')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
