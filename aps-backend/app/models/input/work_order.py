"""APS Local DB — Work Order model.

Redesigned (2026-07-20) to anchor on aps_mps_plan instead of plan_operation/
plan_scenario — those tables have no producer since the scheduler was removed
from the backend. One row per (mps_plan, item_routing) production step that
has an actual work order in flight or already sent to G-System. mps_plan_id
is nullable — some G-System work orders are ad-hoc/manual with no MPS plan
behind them (no planId in the /pd/workorder response).

Lives in aps_input (not aps_result) — it tracks G-System work order state
alongside its MPS source, same domain as aps_mps_plan/aps_item_routing_spec.

`temp_id` is assigned by APS at creation time for PLANNED rows created ahead
of a real G-System work order (see create_planned_work_orders_from_mps_plan);
it's NULL for rows synced straight from G-System, which already carry
`work_order_no`/`gsystem_work_order_id`.
"""

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class WorkOrder(Base):
    __tablename__ = "aps_work_order"
    __table_args__ = (
        UniqueConstraint("mps_plan_id", "item_routing_id", name="uq_aps_work_order_mps_plan_item_routing"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Local idempotency key for PLANNED rows created before G-System has a real work order
    # (see create_planned_work_orders_from_mps_plan). NULL for rows synced straight from
    # G-System's /pd/workorder — those already carry gsystem_work_order_id/work_order_no.
    temp_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True, index=True)

    # Nullable — some G-System work orders are ad-hoc/manual with no MPS plan behind
    # them (no planId in /pd/workorder response); those sync in with mps_plan_id=NULL.
    mps_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_mps_plan.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Denormalized from mps_plan.item_id / item_routing_spec.workcenter_id for query convenience.
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="SET NULL"), nullable=True, index=True
    )
    item_routing_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item_routing_spec.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workcenter_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_workcenter.id", ondelete="SET NULL"), nullable=True, index=True
    )

    work_order_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    work_order_serl: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # `id` field from the G-System POST /pd/workorder/aps/save response.
    gsystem_work_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    work_order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    qty: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)

    # PLANNED (not sent yet) -> SENT (forwarded to G-System) -> CONFIRMED (G-System returned
    # work_order_no/gsystem_work_order_id) -> FAILED (G-System rejected/errored).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PLANNED")
    sync_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
