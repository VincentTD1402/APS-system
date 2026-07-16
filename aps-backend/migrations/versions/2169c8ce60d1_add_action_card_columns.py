"""add action card columns

Revision ID: 2169c8ce60d1
Revises: ef6118a0242f
Create Date: 2026-04-28 08:38:35.000589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2169c8ce60d1'
down_revision: Union[str, Sequence[str], None] = 'ef6118a0242f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── plan_impacted_order: LLM-generated insight ────────────────────────────
    op.add_column(
        'plan_impacted_order',
        sa.Column('llm_insight', sa.Text(), nullable=True),
        schema='aps_result',
    )

    # ── plan_evaluation_action: Action Card fields ────────────────────────────
    # Link to the risk that triggered generation
    op.add_column(
        'plan_evaluation_action',
        sa.Column('impacted_id', sa.String(50), nullable=True),
        schema='aps_result',
    )
    op.create_foreign_key(
        'fk_plan_eval_action_impacted_id',
        'plan_evaluation_action', 'plan_impacted_order',
        ['impacted_id'], ['impacted_id'],
        source_schema='aps_result', referent_schema='aps_result',
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_aps_result_plan_evaluation_action_impacted_id',
        'plan_evaluation_action', ['impacted_id'],
        schema='aps_result',
    )

    # UI display fields
    op.add_column(
        'plan_evaluation_action',
        sa.Column('title', sa.String(255), nullable=True),
        schema='aps_result',
    )
    op.add_column(
        'plan_evaluation_action',
        sa.Column('description', sa.Text(), nullable=True),
        schema='aps_result',
    )

    # Structured parameters from feasibility checker
    op.add_column(
        'plan_evaluation_action',
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema='aps_result',
    )

    # Idempotency: set when action is applied via execute API
    op.add_column(
        'plan_evaluation_action',
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        schema='aps_result',
    )

    # Expand action_type column length (30 → 50) for new types
    op.alter_column(
        'plan_evaluation_action', 'action_type',
        type_=sa.String(50),
        schema='aps_result',
    )

    # Make reason nullable (enabled=True actions have no reason)
    op.alter_column(
        'plan_evaluation_action', 'reason',
        nullable=True,
        schema='aps_result',
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Restore reason to NOT NULL (set empty string for existing NULLs first)
    op.execute(
        "UPDATE aps_result.plan_evaluation_action SET reason = '' WHERE reason IS NULL"
    )
    op.alter_column(
        'plan_evaluation_action', 'reason',
        nullable=False,
        schema='aps_result',
    )

    op.alter_column(
        'plan_evaluation_action', 'action_type',
        type_=sa.String(30),
        schema='aps_result',
    )

    op.drop_column('plan_evaluation_action', 'executed_at', schema='aps_result')
    op.drop_column('plan_evaluation_action', 'parameters', schema='aps_result')
    op.drop_column('plan_evaluation_action', 'description', schema='aps_result')
    op.drop_column('plan_evaluation_action', 'title', schema='aps_result')

    op.drop_index(
        'ix_aps_result_plan_evaluation_action_impacted_id',
        table_name='plan_evaluation_action',
        schema='aps_result',
    )
    op.drop_constraint(
        'fk_plan_eval_action_impacted_id',
        'plan_evaluation_action',
        schema='aps_result',
        type_='foreignkey',
    )
    op.drop_column('plan_evaluation_action', 'impacted_id', schema='aps_result')

    op.drop_column('plan_impacted_order', 'llm_insight', schema='aps_result')
