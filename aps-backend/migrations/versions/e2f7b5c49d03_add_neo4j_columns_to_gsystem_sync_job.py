"""add neo4j stats columns to gsystem_sync_job

Revision ID: e2f7b5c49d03
Revises: d1e6b4a39c02
Create Date: 2026-05-04 09:00:00.000000
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'e2f7b5c49d03'
down_revision: Union[str, Sequence[str], None] = 'd1e6b4a39c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('gsystem_sync_job', sa.Column('neo4j_nodes', sa.Integer(), nullable=False, server_default='0'), schema='aps_result')
    op.add_column('gsystem_sync_job', sa.Column('neo4j_relationships', sa.Integer(), nullable=False, server_default='0'), schema='aps_result')
    op.add_column('gsystem_sync_job', sa.Column('rdf_triples', sa.Integer(), nullable=False, server_default='0'), schema='aps_result')


def downgrade() -> None:
    op.drop_column('gsystem_sync_job', 'rdf_triples', schema='aps_result')
    op.drop_column('gsystem_sync_job', 'neo4j_relationships', schema='aps_result')
    op.drop_column('gsystem_sync_job', 'neo4j_nodes', schema='aps_result')
