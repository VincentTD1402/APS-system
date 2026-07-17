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
        CheckConstraint("status IN ('normal','overload')", name="ck_daily_plan_status"),
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
    # Per-(workcenter, work_date) capacity check result — "normal" | "overload".
    # Computed in daily_plan_builder.rebuild_daily_plan; string (not enum) leaves
    # room for a future 3rd value (e.g. material-shortage).
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")

    mps_plan: Mapped["MpsPlan"] = relationship(foreign_keys=[mps_plan_id])
    item_routing: Mapped["ItemRoutingSpec"] = relationship(foreign_keys=[item_routing_id])
    workcenter: Mapped["WorkCenter"] = relationship(foreign_keys=[workcenter_id])

    def __repr__(self) -> str:
        return f"<DailyPlan wc={self.workcenter_id} date={self.work_date} qty={self.planned_qty}>"
