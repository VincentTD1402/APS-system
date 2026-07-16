"""add parent_scenario_id for simulation branching

Revision ID: 8f2c1a3b4e5d
Revises: 2169c8ce60d1
Create Date: 2026-05-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2c1a3b4e5d'
down_revision: Union[str, Sequence[str], None] = '2169c8ce60d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add parent_scenario_id to link simulation scenarios to their baseline."""
    
    # Add column to plan_scenario
    op.add_column(
        'plan_scenario',
        sa.Column('parent_scenario_id', sa.String(50), nullable=True),
        schema='aps_result',
    )
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_plan_scenario_parent_scenario_id',
        'plan_scenario', 'plan_scenario',
        ['parent_scenario_id'], ['scenario_id'],
        source_schema='aps_result', referent_schema='aps_result',
        ondelete='SET NULL',
    )
    
    # Create index for efficient lookup of simulations by parent
    op.create_index(
        'ix_aps_result_plan_scenario_parent_scenario_id',
        'plan_scenario', ['parent_scenario_id'],
        schema='aps_result',
    )


def downgrade() -> None:
    """Downgrade schema: Remove parent_scenario_id."""
    
    # Drop index
    op.drop_index(
        'ix_aps_result_plan_scenario_parent_scenario_id',
        table_name='plan_scenario',
        schema='aps_result',
    )
    
    # Drop foreign key
    op.drop_constraint(
        'fk_plan_scenario_parent_scenario_id',
        'plan_scenario',
        schema='aps_result',
        type_='foreignkey',
    )
    
    # Drop column
    op.drop_column(
        'plan_scenario',
        'parent_scenario_id',
        schema='aps_result',
    )
