"""APS Local DB — ItemRoutingSpec model.

Synced from G-System GET /pd/itemRoutingMng?itemId={itemId} — 품목별라우팅입력
(item-specific routing input), one row per (item, proc step). itemId is the
G-System business id (Item.gsystem_id).

Naming note: this holds the item-specific routing SPEC (actual work_time/jph
measured for this item on this routing) — distinct from Routing (routing.py,
aps_routing), which is the shared routing template with no item-level
override. Previously named "ItemRouting"; renamed to "...Spec" so it doesn't
read as a duplicate of Routing/RoutingItem.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ItemRoutingSpec(Base):
    """Item-specific routing spec (work_time/jph override) from G-System pd_item_routing."""

    __tablename__ = "aps_item_routing_spec"
    __table_args__ = ({"schema": "aps_input"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # G-System interface record id — unique per (item, proc step)
    gsystem_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="CASCADE"), index=True
    )

    routing_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_routing.id", ondelete="SET NULL"), index=True
    )
    gsystem_routing_id: Mapped[int | None] = mapped_column(Integer)
    routing_no: Mapped[str | None] = mapped_column(String(50))
    routing_name: Mapped[str | None] = mapped_column(String(200))

    workcenter_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_workcenter.id", ondelete="SET NULL"), index=True
    )
    gsystem_workcenter_id: Mapped[int | None] = mapped_column(Integer)

    gsystem_proc_id: Mapped[int | None] = mapped_column(Integer)
    proc_sno: Mapped[int | None] = mapped_column(Integer)
    proc_name: Mapped[str | None] = mapped_column(String(200))
    making_gb: Mapped[str | None] = mapped_column(String(50))
    lead_time: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Standard time per unit (seconds/EA, G-System workTime)
    work_time: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Output rate — EA/HR — computed as 3600 / work_time
    jph: Mapped[float | None] = mapped_column(Numeric(10, 2))
    inspec_type: Mapped[str | None] = mapped_column(String(20))
    inspection_yn: Mapped[bool | None] = mapped_column(Boolean)
    work_ins_yn: Mapped[bool | None] = mapped_column(Boolean)
    sample_qty: Mapped[float | None] = mapped_column(Numeric(10, 2))
    stock_yn: Mapped[bool | None] = mapped_column(Boolean)

    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    routing: Mapped["Routing | None"] = relationship(foreign_keys=[routing_id])
    workcenter: Mapped["WorkCenter | None"] = relationship(foreign_keys=[workcenter_id])

    def __repr__(self) -> str:
        return f"<ItemRoutingSpec item_id={self.item_id!r} proc_sno={self.proc_sno} jph={self.jph}>"
