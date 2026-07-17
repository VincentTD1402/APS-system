"""APS Local DB — BOM (Bill of Materials) model.

Merged table: one row = one parent/component link (former header+line
split into `aps_bom` + `aps_bom_component` collapsed into a single
`aps_bom` table — the header added no value beyond `parent_item_id`,
which now lives directly on each line).
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class BOM(Base):
    """One BOM line: parent item → component item + quantities."""

    __tablename__ = "aps_bom"
    __table_args__ = (
        UniqueConstraint("parent_item_id", "component_item_id", name="uq_aps_bom_parent_component"),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)
    component_item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)
    qty1: Mapped[float | None] = mapped_column(Numeric(18, 4))
    qty2: Mapped[float | None] = mapped_column(Numeric(18, 4))
    bom_seq: Mapped[int | None] = mapped_column(Integer)

    # G-System interface ids
    gsystem_if_id: Mapped[int | None] = mapped_column(Integer)
    gsystem_bom_id: Mapped[int | None] = mapped_column(Integer)

    # Denormalized codes
    parent_item_no: Mapped[str | None] = mapped_column(String(50))
    component_item_no: Mapped[str | None] = mapped_column(String(50))
    bom_level: Mapped[str | None] = mapped_column(String(10))
    delivery_type: Mapped[str | None] = mapped_column(String(50))
    delivery_type_name: Mapped[str | None] = mapped_column(String(100))
    rev_no: Mapped[int | None] = mapped_column(Integer)

    # Validity dates (raw YYYYMMDD strings, NOT parsed to Date)
    start_date: Mapped[str | None] = mapped_column(String(8))
    end_date: Mapped[str | None] = mapped_column(String(8))

    # Interface receipt / audit fields
    if_recv_yn: Mapped[bool | None] = mapped_column(Boolean)
    if_recv_dt: Mapped[datetime | None] = mapped_column(DateTime)
    reg_dt: Mapped[datetime | None] = mapped_column(DateTime)
    reg_user_id: Mapped[int | None] = mapped_column(Integer)
    mod_dt: Mapped[datetime | None] = mapped_column(DateTime)
    mod_user_id: Mapped[int | None] = mapped_column(Integer)
    corp_id: Mapped[int | None] = mapped_column(Integer)
    biz_id: Mapped[int | None] = mapped_column(Integer)
    if_status: Mapped[str | None] = mapped_column(String(10))

    parent_item: Mapped["Item"] = relationship(
        back_populates="bom_parent_links", foreign_keys=[parent_item_id]
    )
    component_item: Mapped["Item"] = relationship(
        back_populates="bom_component_links", foreign_keys=[component_item_id]
    )
