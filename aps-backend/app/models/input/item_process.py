"""APS Local DB — ItemProcessStep model.

Maps G-System item_process: which processes an item goes through and in what order.
Sources:
  - /pd/itemProcess/aps/pending (ifType: item_process) — delta sync, no workTime
  - /pd/routingMng/aps/itemProcessListByRouting — full load per routing, provides workTime

Naming note: pairs with RoutingStep (routing.py, aps_routing_step) — that model
is a step scoped to a ROUTING (shared by every item on it); this one is a step
scoped to an ITEM (can override work_time per routing). Previously named
"ItemProcess"; renamed to make the "step" concept and the routing/item scoping
explicit and symmetric.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ItemProcessStep(Base):
    """One process step assigned to an item (item-level process plan).

    Derived from G-System pd_item_process.
    Distinct from aps_routing_step (which belongs to a routing, not an item directly).

    routing_id + work_time_hours are populated by itemProcessListByRouting (not pending).
    The same item can appear in multiple routings with different work times.
    Unique key includes routing_id to allow that.
    """

    __tablename__ = "aps_item_process_step"
    __table_args__ = (
        UniqueConstraint("routing_id", "item_id", "proc_sno", name="uq_item_process_routing_item_sno"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False, index=True)
    # Routing context — set when synced from itemProcessListByRouting; null for pending-only records
    routing_id: Mapped[int | None] = mapped_column(ForeignKey("aps_input.aps_routing.id"), index=True)
    # G-System process integer ID (references process master)
    gsystem_proc_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Sequence number of this process within the item's process list
    proc_sno: Mapped[int] = mapped_column(Integer, nullable=False)
    # G-System making category code (e.g. "10401002")
    making_gb: Mapped[str | None] = mapped_column(String(20))
    inspection_yn: Mapped[bool | None] = mapped_column(Boolean)
    work_ins_yn: Mapped[bool | None] = mapped_column(Boolean)
    stock_yn: Mapped[bool | None] = mapped_column(Boolean)
    rev_no: Mapped[int | None] = mapped_column(Integer)
    # Item-specific work time for this process step (minutes → hours via conversion)
    # Set from itemProcessListByRouting; null when source is pending endpoint only
    work_time_hours: Mapped[float | None] = mapped_column(Numeric(10, 4))

    item: Mapped["Item"] = relationship(back_populates="item_process_steps")
    routing: Mapped["Routing"] = relationship()

    def __repr__(self) -> str:
        return f"<ItemProcessStep routing={self.routing_id} item={self.item_id} sno={self.proc_sno} proc={self.gsystem_proc_id}>"
