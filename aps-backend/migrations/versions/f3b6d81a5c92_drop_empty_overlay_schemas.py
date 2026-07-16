"""drop empty aps_input_overlay/aps_result_overlay schemas

Revision ID: f3b6d81a5c92
Revises: e8c1f4a92b07
Create Date: 2026-07-16

Both schemas were emptied of all tables in a prior migration
(d4a7f92e6c31 — drop orphaned evaluation/material/version/overlay tables).
Dropping the now-empty schema containers themselves.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f3b6d81a5c92'
down_revision = 'e8c1f4a92b07'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS aps_input_overlay")
    op.execute("DROP SCHEMA IF EXISTS aps_result_overlay")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_input_overlay")
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_result_overlay")
