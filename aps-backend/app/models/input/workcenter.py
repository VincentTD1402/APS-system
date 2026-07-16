"""APS Local DB — WorkCenter model."""

from typing import List
from sqlalchemy import CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class WorkCenter(Base):
    """Normalized workcenter from G-System pd_workcenter."""

    __tablename__ = "aps_workcenter"
    __table_args__ = (
        CheckConstraint("std_capa IS NULL OR std_capa >= 0", name="ck_workcenter_std_capa_non_negative"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Original G-System workcenter_id (for traceability)
    gsystem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    workcenter_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    workcenter_name: Mapped[str | None] = mapped_column(String(200))
    workshop_cd: Mapped[str | None] = mapped_column(String(50))
    # Default operating capacity in MINUTES/day (base 480 = 8h). Effective capacity
    # is this value scaled by the sum of its equipment cycle_factor (ST conversion).
    std_capa: Mapped[float | None] = mapped_column(Numeric(10, 2), default=480, server_default="480")

    routing_steps: Mapped[List["RoutingStep"]] = relationship(back_populates="workcenter")
    # Plan operations referencing this workcenter
    plan_operations: Mapped[List["PlanOperation"]] = relationship(back_populates="workcenter")
    equipment: Mapped[List["Equipment"]] = relationship(
        back_populates="workcenter", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkCenter {self.workcenter_no!r}>"
