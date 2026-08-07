"""add mps dates push status to work_order

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-07-29 00:00:00

Tracks the outcome of pushing a dispatched work order's MPS line dates back
to G-System (/pd/prodPlanMpsMng/aps/updateDates), separate from the work
order dispatch's own sync_status/response_json/sent_at.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'work_order',
        sa.Column('mps_dates_sync_status', sa.String(length=20), nullable=True),
        schema='aps_input',
    )
    op.add_column(
        'work_order',
        sa.Column('mps_dates_response_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='aps_input',
    )
    op.add_column(
        'work_order',
        sa.Column('mps_dates_sent_at', sa.DateTime(timezone=True), nullable=True),
        schema='aps_input',
    )


def downgrade() -> None:
    op.drop_column('work_order', 'mps_dates_sent_at', schema='aps_input')
    op.drop_column('work_order', 'mps_dates_response_json', schema='aps_input')
    op.drop_column('work_order', 'mps_dates_sync_status', schema='aps_input')
