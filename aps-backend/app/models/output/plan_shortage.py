"""APS Local DB — Plan Shortage model."""

from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import String, Date, ForeignKey, Numeric, Index, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class PlanShortage(Base):
    """Material shortage detections."""
    __tablename__ = "plan_shortage"
    __table_args__ = {"schema": "aps_result"}

    shortage_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_order.plan_id", ondelete="CASCADE"), index=True, nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), index=True, nullable=False)
    op_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    need_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    required_qty: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    available_qty: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    shortage_qty: Mapped[float] = mapped_column(Numeric(15, 4), index=True, nullable=False)
    cause: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    scenario_id: Mapped[str] = mapped_column(ForeignKey("aps_result.plan_scenario.scenario_id"), index=True, nullable=False)
    run_id: Mapped[Optional[str]] = mapped_column(String(50))
    impact_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order: Mapped["PlanOrder"] = relationship(back_populates="shortages")
    item: Mapped["Item"] = relationship(back_populates="plan_shortages")
