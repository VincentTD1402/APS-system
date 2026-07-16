"""merge alembic heads

Revision ID: f7a8b9c0d1e2
Revises: c2d3e4f5a6b7, 8f2c1a3b4e5d, e35c6fa9264b
Create Date: 2026-05-04 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = (
    'c2d3e4f5a6b7',
    '8f2c1a3b4e5d',
    'e35c6fa9264b',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branch heads without changing schema."""


def downgrade() -> None:
    """No-op downgrade for merge revision."""
