"""APS Local DB — Routing, RoutingItem (join), and RoutingStep models.

Naming note (routing-level vs item-level process data):
  Routing/RoutingStep/RoutingItem here define the SHARED routing template — one
  RoutingStep (aps_routing_step) is one process step of a routing, reused by
  every item that follows that routing. This is distinct from ItemProcessStep
  (aps_item_process_step, item_process.py) and ItemRoutingSpec
  (aps_item_routing_spec, item_routing.py), which hold per-item overrides
  (e.g. an item-specific work_time/jph that differs from the routing default).
  RoutingStep was previously named "Operation" — renamed for clarity paired
  with ItemProcessStep (both are "a step"), scoped by routing vs item.
"""

from typing import List
from sqlalchemy import CheckConstraint, Integer, Numeric, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Routing(Base):
    """Normalized routing from G-System pd_if_aps_routing / pd_routing."""

    __tablename__ = "aps_routing"
    __table_args__ = {"schema": "aps_input"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Original G-System routing_id (integer PK in mes_dev) — used as join key
    gsystem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # routing_no is nullable in G-System (many routings have no number)
    routing_no: Mapped[str | None] = mapped_column(String(50))
    routing_name: Mapped[str | None] = mapped_column(String(200))
    # G-System code: "14681001" (internal) or "14681002" (outsource)
    routing_type_cd: Mapped[str | None] = mapped_column(String(20))
    std_capa: Mapped[float | None] = mapped_column(Numeric(10, 2))

    routing_items: Mapped[List["RoutingItem"]] = relationship(back_populates="routing")
    routing_steps: Mapped[List["RoutingStep"]] = relationship(
        back_populates="routing", order_by="RoutingStep.process_seq"
    )
    # Plan operations referencing this routing
    plan_operations: Mapped[List["PlanOperation"]] = relationship(back_populates="routing")

    def __repr__(self) -> str:
        return f"<Routing gsystem_id={self.gsystem_id} {self.routing_name!r}>"


class RoutingItem(Base):
    """Mapping: which items are produced via which routing.

    Derived from G-System pd_routing_item (routing_id ↔ item_id).
    Join key is gsystem_id (integer), not routing_no (nullable).
    """

    __tablename__ = "aps_routing_item"
    __table_args__ = (UniqueConstraint("routing_id", "item_id"), {"schema": "aps_input"})

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routing_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_routing.id"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)

    routing: Mapped["Routing"] = relationship(back_populates="routing_items")
    item: Mapped["Item"] = relationship(back_populates="routing_items")


class RoutingStep(Base):
    """One process step within a ROUTING (shared template, not item-specific).

    Derived from G-System pd_routing_process.
    work_time and setup_time stored as decimal hours (converted from HHMM string).
    Previously named "Operation" — see module docstring for the routing-level
    vs item-level naming rationale (pairs with ItemProcessStep).
    """

    __tablename__ = "aps_routing_step"
    __table_args__ = (
        UniqueConstraint("routing_id", "process_seq"),
        CheckConstraint("work_time_hours IS NULL OR work_time_hours >= 0", name="ck_operation_work_time_non_negative"),
        CheckConstraint("setup_time_hours IS NULL OR setup_time_hours >= 0", name="ck_operation_setup_time_non_negative"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    routing_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_routing.id"), nullable=False)
    process_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    # Original G-System process_id for traceability
    gsystem_process_id: Mapped[int | None] = mapped_column(Integer)
    proc_no: Mapped[str | None] = mapped_column(String(50))
    proc_name: Mapped[str | None] = mapped_column(String(200))
    workcenter_id: Mapped[int | None] = mapped_column(ForeignKey("aps_input.aps_workcenter.id"))
    # Decimal hours — converted from G-System HHMM format (e.g. "1015" → 10.25)
    work_time_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))
    setup_time_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))

    routing: Mapped["Routing"] = relationship(back_populates="routing_steps")
    workcenter: Mapped["WorkCenter"] = relationship(back_populates="routing_steps")
    plan_operations: Mapped[List["PlanOperation"]] = relationship(back_populates="routing_step")

    def __repr__(self) -> str:
        return f"<RoutingStep routing_id={self.routing_id} seq={self.process_seq}>"
