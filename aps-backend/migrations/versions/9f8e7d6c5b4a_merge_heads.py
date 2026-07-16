"""merge heads

Revision ID: 9f8e7d6c5b4a
Revises: 51336be2a757, ddaa67fe83f8
Create Date: 2026-05-04 00:00:00

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '9f8e7d6c5b4a'
down_revision: Union[str, Sequence[str], None] = ('51336be2a757', 'ddaa67fe83f8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branch heads without changing schema."""


def downgrade() -> None:
    """No-op downgrade for merge revision."""