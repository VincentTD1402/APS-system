"""APS Local DB — Daily Plan model.

Computed (not synced) — backward-fill breakdown of each MPS plan line's
plan_qty into per-day quantities per routing step, used by KPI3 (workcenter
load). Rebuilt wholesale on every sync (see daily_plan_builder.rebuild_daily_plan).
"""

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DailyPlan(Base):
    """Per-day quantity breakdown of an MPS plan line's routing step."""

    __tablename__ = "aps_daily_plan"
    __table_args__ = (
        CheckConstraint(
            "status IN ('normal','overload','material-shortage','urgent')",
            name="ck_daily_plan_status",
        ),
        {"schema": "aps_result"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mps_plan_id: Mapped[int] = mapped_column(
        ForeignKey("aps_input.aps_mps_plan.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_routing_id: Mapped[int] = mapped_column(
        ForeignKey("aps_input.aps_item_routing_spec.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workcenter_id: Mapped[int] = mapped_column(
        ForeignKey("aps_input.aps_workcenter.id", ondelete="CASCADE"), index=True, nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    planned_qty: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    # Combined risk flag: 'normal' | 'overload' | 'material-shortage' | 'urgent'
    # (urgent = both overload and material shortage). Overload set by
    # rebuild_daily_plan; material-shortage/urgent set by apply_daily_material_shortage.
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    # Raw-material quantity short for this (mps_plan, work_date), from the backward
    # material running-balance (stock consumed earliest-day-first → shortfall lands
    # on the latest production days). 0 = no material shortage. The API exposes it
    # alongside `status` as a `statuses` array (overload and/or material-shortage).
    material_shortage_qty: Mapped[float] = mapped_column(
        Numeric(18, 4), nullable=False, server_default="0"
    )

    mps_plan: Mapped["MpsPlan"] = relationship(foreign_keys=[mps_plan_id])
    item_routing: Mapped["ItemRoutingSpec"] = relationship(foreign_keys=[item_routing_id])
    workcenter: Mapped["WorkCenter"] = relationship(foreign_keys=[workcenter_id])

    def __repr__(self) -> str:
        return f"<DailyPlan wc={self.workcenter_id} date={self.work_date} qty={self.planned_qty}>"
