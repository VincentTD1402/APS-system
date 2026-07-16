"""APS Local DB — Plan Order and Plan Operation models."""

from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import String, DateTime, Date, ForeignKey, Integer, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PlanOrder(Base):
    """Represent a scheduled production order."""
    __tablename__ = "plan_order"
    __table_args__ = {"schema": "aps_result"}

    plan_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False)
    demand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("aps_input.aps_demand.id"), index=True)
    demand_line_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    planned_start_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    planned_finish_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    planned_ship_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    late_days: Mapped[int] = mapped_column(Integer, nullable=False)

    run_id: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    priority_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    scenario: Mapped["PlanScenario"] = relationship(back_populates="orders")
    demand: Mapped[Optional["Demand"]] = relationship(back_populates="plan_orders")
    operations: Mapped[List["PlanOperation"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    shortages: Mapped[List["PlanShortage"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class PlanOperation(Base):
    """Detailed routing steps for a plan_order."""
    __tablename__ = "plan_operation"
    __table_args__ = {"schema": "aps_result"}

    plan_op_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), nullable=False)
    op_code: Mapped[str] = mapped_column(String(50), nullable=False)
    workcenter_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_workcenter.id"), index=True, nullable=False)
    # FK to aps_routing_step.id (Integer)
    operation_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_routing_step.id"), nullable=False, index=True)
    # Synced with aps_routing.id (Integer)
    routing_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_routing.id"), nullable=False)

    planned_start_dt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    planned_end_dt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    load_minutes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    scenario_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(50))
    sequence: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order: Mapped["PlanOrder"] = relationship(back_populates="operations")
    routing_step: Mapped["RoutingStep"] = relationship(back_populates="plan_operations")
    workcenter: Mapped["WorkCenter"] = relationship(back_populates="plan_operations")
    routing: Mapped["Routing"] = relationship(back_populates="plan_operations")
