"""create calendar overlay table

Revision ID: b1c2d3a4b5c6
Revises: f7a8b9c0d1e2
Create Date: 2026-05-04 00:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS aps_input_overlay")

    op.create_table(
        'aps_calendar_overlay',
        sa.Column('scenario_id', sa.String(50), primary_key=True),
        sa.Column('work_date', sa.Date(), primary_key=True),
        sa.Column('day_of_week_cd', sa.String(20)),
        sa.Column('work_gb_cd', sa.String(20)),
        sa.Column('is_holiday', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('work_hours', sa.Numeric(6, 4), nullable=False, server_default='0.0'),
        sa.CheckConstraint('work_hours >= 0', name='ck_calendar_overlay_work_hours_non_negative'),
        schema='aps_input_overlay'
    )


def downgrade() -> None:
    op.drop_table('aps_calendar_overlay', schema='aps_input_overlay')
