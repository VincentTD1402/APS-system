from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class WorkOrder(Base):
    __tablename__ = "work_order"
    __table_args__ = (
        UniqueConstraint("scenario_id", "plan_op_id", name="uq_work_order_scenario_plan_op"),
        {"schema": "aps_result"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_scenario.scenario_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_op_id: Mapped[str] = mapped_column(
        ForeignKey("aps_result.plan_operation.plan_op_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    plan_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    work_order_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    work_order_serl: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    work_order_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    item_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    workcenter_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
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
