"""APS Local DB — impacted orders produced by planning/evaluation."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class PlanImpactedOrder(Base):
    """Orders impacted by shortages/overload/risk in a scenario."""

    __tablename__ = "plan_impacted_order"
    __table_args__ = (
        Index("idx_plan_impacted_order_scenario", "scenario_id"),
        Index("idx_plan_impacted_order_plan", "plan_id"),
        Index("idx_plan_impacted_order_reason", "reason_type"),
        {"schema": "aps_result"},
    )

    impacted_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_scenario.scenario_id"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Optional reference to source demand for easier FE filtering.
    demand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("aps_input.aps_demand.id"), index=True)

    # E.g. MATERIAL_SHORTAGE | WC_OVERLOAD | DELIVERY_RISK
    reason_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # INFO | WARNING | CRITICAL
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(String(500))

    # LLM-generated insight for this risk — populated by ActionCardService
    llm_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
