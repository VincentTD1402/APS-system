"""APS Local DB — workcenter load snapshots for FE heatmap."""

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class WorkcenterLoad(Base):
    """Daily load snapshot per workcenter (and optional operation)."""

    __tablename__ = "workcenter_load"
    __table_args__ = (
        Index("idx_workcenter_load_scenario_date", "scenario_id", "work_date"),
        Index("idx_workcenter_load_workcenter", "workcenter_id"),
        Index("idx_workcenter_load_operation", "operation_id"),
        {"schema": "aps_result"},
    )

    load_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False
    )
    run_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    workcenter_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_workcenter.id"), nullable=False)

    # Optional operation-level line for drill-down.
    operation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("aps_input.aps_routing_step.id"), index=True)
    proc_name: Mapped[Optional[str]] = mapped_column(String(200))

    used_minutes: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    capacity_minutes: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    load_percent: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)

    overloaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # normal | warning | overload | off
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
