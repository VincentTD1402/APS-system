"""daily_plan: allow status material-shortage/urgent

Revision ID: a8d1e6f4c3b9
Revises: f7b3c9e2a5d4
Create Date: 2026-07-18 14:15:00

status now carries the combined risk flag: normal | overload | material-shortage
| urgent (both overload and material shortage).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a8d1e6f4c3b9"
down_revision: Union[str, Sequence[str], None] = "f7b3c9e2a5d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_daily_plan_status", "aps_daily_plan", schema="aps_result", type_="check")
    op.create_check_constraint(
        "ck_daily_plan_status", "aps_daily_plan",
        "status IN ('normal','overload','material-shortage','urgent')",
        schema="aps_result",
    )


def downgrade() -> None:
    op.drop_constraint("ck_daily_plan_status", "aps_daily_plan", schema="aps_result", type_="check")
    # Collapse the new values back so the old constraint holds.
    op.execute(
        "UPDATE aps_result.aps_daily_plan SET status='overload' WHERE status='urgent'"
    )
    op.execute(
        "UPDATE aps_result.aps_daily_plan SET status='normal' WHERE status='material-shortage'"
    )
    op.create_check_constraint(
        "ck_daily_plan_status", "aps_daily_plan",
        "status IN ('normal','overload')",
        schema="aps_result",
    )
