"""merge final heads (work_date branch + overlay branch)

Brings together:
- 7f4bc6f20887: data_source column chain via e2f7 -> b1c8 warnings -> 7f4bc6
- 9f8e7d6c5b4a: merge of 51336 work_date + ddaa overlay/GSystem branch

Revision ID: a8b9c0d1e2f3
Revises: 7f4bc6f20887, 9f8e7d6c5b4a
Create Date: 2026-05-05

"""
from typing import Sequence, Union

revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = ("7f4bc6f20887", "9f8e7d6c5b4a")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge branch heads; no schema change."""


def downgrade() -> None:
    """No-op for merge revision."""
