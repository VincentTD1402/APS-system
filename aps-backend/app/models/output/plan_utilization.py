"""APS Local DB — Plan Utilization model."""

from datetime import date, datetime
from typing import Optional
from sqlalchemy import Integer, String, Date, ForeignKey, Numeric, UniqueConstraint, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PlanUtilization(Base):
    """Daily utilization per workcenter."""
    __tablename__ = "plan_utilization"
    __table_args__ = (
        UniqueConstraint("scenario_id", "workcenter_id", "plan_date", name="idx_plan_utilization_scenario_workcenter_date"),
        Index("idx_plan_utilization_scenario", "scenario_id"),
        Index("idx_plan_utilization_workcenter", "workcenter_id"),
        Index("idx_plan_utilization_date", "plan_date"),
        {"schema": "aps_result"}
    )

    utilization_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False)
    workcenter_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    utilization_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    available_capacity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    used_capacity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    scenario: Mapped["PlanScenario"] = relationship(back_populates="utilizations")