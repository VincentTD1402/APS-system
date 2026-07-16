"""APS Local DB — Demand (production plan) model."""

from datetime import date
from typing import List, Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Demand(Base):
    """Production demand from G-System pd_prodplan."""

    __tablename__ = "aps_demand"
    __table_args__ = {"schema": "aps_input"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)
    # When set, this routing must be one of the item's routings (see aps_routing_item).
    routing_id: Mapped[int | None] = mapped_column(ForeignKey("aps_input.aps_routing.id"), nullable=True)
    # Customer reference — nullable so existing synced demands without customer still work.
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("aps_input.aps_customer.id"), nullable=True)
    plan_qty: Mapped[float | None] = mapped_column(Numeric(18, 4))
    plan_date: Mapped[date | None] = mapped_column(Date)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    # "notCreated" | "created" from G-System ifStatus
    status_cd: Mapped[str | None] = mapped_column(String(20))
    # Data source that created this demand: "mock", "gsystem", future "ksystem"
    data_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="gsystem", index=True
    )

    item: Mapped["Item"] = relationship(back_populates="demands")
    routing: Mapped["Routing | None"] = relationship(foreign_keys=[routing_id])
    customer: Mapped["Customer | None"] = relationship(back_populates="demands")
    plan_orders: Mapped[List["PlanOrder"]] = relationship(back_populates="demand")

    def __repr__(self) -> str:
        return f"<Demand {self.plan_no!r} qty={self.plan_qty}>"
