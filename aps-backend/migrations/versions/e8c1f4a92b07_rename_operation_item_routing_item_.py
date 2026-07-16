"""rename aps_operation/aps_item_routing/aps_item_process for clarity

Revision ID: e8c1f4a92b07
Revises: d4a7f92e6c31
Create Date: 2026-07-16

Table names were confusing because two independent concepts (routing-level
step vs item-level step, routing template vs item-specific routing spec) used
near-identical names. Renamed to make each table's scope explicit:

  aps_operation      -> aps_routing_step       (a process step OF A ROUTING)
  aps_item_routing   -> aps_item_routing_spec  (item-specific routing spec: work_time/jph)
  aps_item_process   -> aps_item_process_step  (a process step OF AN ITEM)

Data-only rename (ALTER TABLE ... RENAME) — no column/data changes, no FK
changes needed since Postgres updates FK targets automatically on rename.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e8c1f4a92b07'
down_revision = 'd4a7f92e6c31'
branch_labels = None
depends_on = None

_RENAMES = [
    ("aps_operation", "aps_routing_step"),
    ("aps_item_routing", "aps_item_routing_spec"),
    ("aps_item_process", "aps_item_process_step"),
]


def upgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.rename_table(old_name, new_name, schema="aps_input")


def downgrade() -> None:
    for old_name, new_name in _RENAMES:
        op.rename_table(new_name, old_name, schema="aps_input")
