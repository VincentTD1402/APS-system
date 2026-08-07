"""APS Local DB — ItemRoutingSpec model.

Synced from G-System GET /pd/itemRoutingMng?itemId={itemId} — 품목별라우팅입력
(item-specific routing input), one row per (item, proc step). itemId is the
G-System business id (Item.gsystem_id). This is the ONLY routing/process-step
source APS uses — no routingProcessList, itemProcessListByRouting, or the
pending routing/routing_item/routing_process/item_process feeds (all removed;
those fed aps_routing/aps_routing_item/aps_routing_step/aps_item_process_step,
which had no real downstream consumer and were dropped).

Column set mirrors the verified live response fields exactly — verified by
scanning itemRoutingMng across all 150 aps_item rows (69 routing rows), not
just a handful, after an earlier pass wrongly dropped fields (routingId,
routingNo/Nm, routingTypeCd, inspecType, leadTime, sampleQty) that just
happened to be absent on the first few items sampled.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ItemRoutingSpec(Base):
    """Item-specific routing spec (work_time/jph) from G-System pd_item_routing."""

    __tablename__ = "aps_item_routing_spec"
    __table_args__ = ({"schema": "aps_input"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # G-System interface record id (response "id") — unique per (item, proc step)
    gsystem_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="CASCADE"), index=True
    )
    # Raw response itemNo/itemNm — denormalized copy, kept because "save the
    # whole response" — item_id join already gives the same via aps_item.
    item_no: Mapped[str | None] = mapped_column(String(50))
    item_name: Mapped[str | None] = mapped_column(String(200))

    # Workcenter is "oscustId"/"custNm" on this endpoint (NOT "workcenterId"/
    # "workcenterNm" like other endpoints) — verified against live response.
    workcenter_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_workcenter.id", ondelete="SET NULL"), index=True
    )
    gsystem_workcenter_id: Mapped[int | None] = mapped_column(Integer)
    workcenter_name_raw: Mapped[str | None] = mapped_column(String(200))

    gsystem_proc_id: Mapped[int | None] = mapped_column(Integer)
    proc_sno: Mapped[int | None] = mapped_column(Integer)
    proc_name: Mapped[str | None] = mapped_column(String(200))
    making_gb: Mapped[str | None] = mapped_column(String(50))

    # Routing this step belongs to — G-System business id + raw denormalized
    # fields (routingId/routingNo/routingNm/routingTypeCd/routingGroupCd).
    # No local FK — aps_routing (the shared routing template table) was
    # dropped as dead code; this is just the raw reference id/name verbatim.
    gsystem_routing_id: Mapped[int | None] = mapped_column(Integer)
    routing_no: Mapped[str | None] = mapped_column(String(50))
    routing_name: Mapped[str | None] = mapped_column(String(200))
    routing_type_cd: Mapped[str | None] = mapped_column(String(20))
    routing_group_cd: Mapped[str | None] = mapped_column(String(20))

    # Standard time per unit (seconds/EA, G-System workTime) — present only
    # when actually entered upstream.
    work_time: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Output rate — EA/HR — computed as 3600 / work_time
    jph: Mapped[float | None] = mapped_column(Numeric(10, 2))
    lead_time: Mapped[int | None] = mapped_column(Integer)

    inspection_yn: Mapped[bool | None] = mapped_column(Boolean)
    inspec_type: Mapped[str | None] = mapped_column(String(20))
    inspec_period: Mapped[str | None] = mapped_column(String(20))
    sample_qty: Mapped[int | None] = mapped_column(Integer)
    work_ins_yn: Mapped[bool | None] = mapped_column(Boolean)
    stock_yn: Mapped[bool | None] = mapped_column(Boolean)
    loss_rate: Mapped[float | None] = mapped_column(Numeric(10, 2))
    tool_id: Mapped[int | None] = mapped_column(Integer)
    remark: Mapped[str | None] = mapped_column(String(500))

    # Remaining raw response fields — kept verbatim per "save the whole response".
    corp_id: Mapped[int | None] = mapped_column(Integer)
    corp_name: Mapped[str | None] = mapped_column(String(200))
    biz_id: Mapped[int | None] = mapped_column(Integer)
    item_cls1: Mapped[str | None] = mapped_column(String(50))
    reg_dt: Mapped[datetime | None] = mapped_column(DateTime)
    reg_user_id: Mapped[int | None] = mapped_column(Integer)
    reg_user_name: Mapped[str | None] = mapped_column(String(100))

    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    workcenter: Mapped["WorkCenter | None"] = relationship(foreign_keys=[workcenter_id])

    def __repr__(self) -> str:
        return f"<ItemRoutingSpec item_id={self.item_id!r} proc_sno={self.proc_sno} jph={self.jph}>"
