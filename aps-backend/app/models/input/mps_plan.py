"""APS Local DB — MPS Plan model.

Synced from G-System GET /pd/prodPlanMpsMng?pareaId={pareaId} — the master
production schedule (MPS), richer than the pd/prodplan/aps/pending pending-queue
feed already synced into aps_demand (has plan_start/end_date, routingId, itemRev).
"""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MpsPlan(Base):
    """Master production schedule entry from G-System pd_prodplan_mps."""

    __tablename__ = "aps_mps_plan"
    __table_args__ = ({"schema": "aps_input"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # G-System interface record id — unique per MPS plan line (upsert key)
    gsystem_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    plan_no: Mapped[str | None] = mapped_column(String(50), index=True)
    dmd_no: Mapped[str | None] = mapped_column(String(50))

    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="SET NULL"), index=True
    )
    gsystem_item_id: Mapped[int | None] = mapped_column(Integer, index=True)
    item_rev: Mapped[int | None] = mapped_column(Integer)

    routing_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_routing.id", ondelete="SET NULL"), index=True
    )
    gsystem_routing_id: Mapped[int | None] = mapped_column(Integer)

    parea_id: Mapped[int | None] = mapped_column(Integer, index=True)

    plan_qty: Mapped[float | None] = mapped_column(Numeric(18, 4))
    order_qty: Mapped[float | None] = mapped_column(Numeric(18, 4))

    plan_date: Mapped[date | None] = mapped_column(Date)
    plan_start_date: Mapped[date | None] = mapped_column(Date)
    plan_end_date: Mapped[date | None] = mapped_column(Date)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    prod_end_date: Mapped[date | None] = mapped_column(Date)

    status_cd: Mapped[str | None] = mapped_column(String(20))
    plan_gbn: Mapped[str | None] = mapped_column(String(20))
    bom_yn: Mapped[bool | None] = mapped_column(Boolean)
    mrp_calc_yn: Mapped[bool | None] = mapped_column(Boolean)
    from_work_plan_yn: Mapped[bool | None] = mapped_column(Boolean)

    wbs_id: Mapped[str | None] = mapped_column(String(50))
    wbs_dtl: Mapped[str | None] = mapped_column(String(50))
    project_no: Mapped[str | None] = mapped_column(String(50))
    project_nm: Mapped[str | None] = mapped_column(String(200))
    po_no: Mapped[str | None] = mapped_column(String(50))

    item: Mapped["Item | None"] = relationship(foreign_keys=[item_id])
    routing: Mapped["Routing | None"] = relationship(foreign_keys=[routing_id])

    def __repr__(self) -> str:
        return f"<MpsPlan {self.plan_no!r} item_rev={self.item_rev}>"
