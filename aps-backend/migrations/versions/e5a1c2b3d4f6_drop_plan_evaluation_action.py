"""drop plan_evaluation_action

Revision ID: e5a1c2b3d4f6
Revises: b7c8d9e0f1a2
Create Date: 2026-08-08 00:00:00

The table held LLM-generated action cards for the scenario-based planning
subsystem. Its only reader was services/llm/suggestion_service.py, which has
been removed, and nothing ever wrote to it — so it was always empty in practice.
The AI suggestion panel derives everything from aps_daily_plan and
aps_material_shortage instead, and stores nothing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e5a1c2b3d4f6'
down_revision = 'b7c8d9e0f1a2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('plan_evaluation_action', schema='aps_result')


def downgrade() -> None:
    op.create_table(
        'plan_evaluation_action',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('scenario_id', sa.String(length=50), nullable=False),
        sa.Column('plan_id', sa.String(length=50), nullable=True),
        sa.Column('impacted_id', sa.String(length=50), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('param_hash', sa.String(length=64), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='aps_result',
    )
    op.create_index('ix_aps_result_plan_evaluation_action_scenario_id',
                    'plan_evaluation_action', ['scenario_id'], schema='aps_result')
    op.create_index('ix_aps_result_plan_evaluation_action_plan_id',
                    'plan_evaluation_action', ['plan_id'], schema='aps_result')
    op.create_index('ix_aps_result_plan_evaluation_action_impacted_id',
                    'plan_evaluation_action', ['impacted_id'], schema='aps_result')
    op.create_index('ix_aps_result_plan_evaluation_action_action_type',
                    'plan_evaluation_action', ['action_type'], schema='aps_result')
    op.create_index('ix_aps_result_plan_evaluation_action_enabled',
                    'plan_evaluation_action', ['enabled'], schema='aps_result')
    op.create_index('uq_action_impacted_type_hash', 'plan_evaluation_action',
                    ['impacted_id', 'action_type', 'param_hash'],
                    unique=True, schema='aps_result')
