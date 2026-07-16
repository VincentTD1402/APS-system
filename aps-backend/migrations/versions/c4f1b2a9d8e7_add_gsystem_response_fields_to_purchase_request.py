"""add gsystem response fields to purchase_request

Revision ID: c4f1b2a9d8e7
Revises: b3e9f4c2a1d0
Create Date: 2026-05-08 13:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4f1b2a9d8e7"
down_revision: Union[str, Sequence[str], None] = "b3e9f4c2a1d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "purchase_request",
        sa.Column("ext_id", sa.Integer(), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("req_no", sa.String(length=100), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("corp_id", sa.Integer(), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("biz_id", sa.Integer(), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("ext_status", sa.String(length=20), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        schema="aps_result",
    )
    op.add_column(
        "purchase_request",
        sa.Column("sync_status", sa.String(length=20), nullable=True),
        schema="aps_result",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("purchase_request", "sync_status", schema="aps_result")
    op.drop_column("purchase_request", "sent_at", schema="aps_result")
    op.drop_column("purchase_request", "response_json", schema="aps_result")
    op.drop_column("purchase_request", "ext_status", schema="aps_result")
    op.drop_column("purchase_request", "biz_id", schema="aps_result")
    op.drop_column("purchase_request", "corp_id", schema="aps_result")
    op.drop_column("purchase_request", "req_no", schema="aps_result")
    op.drop_column("purchase_request", "ext_id", schema="aps_result")
