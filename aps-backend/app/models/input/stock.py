"""APS Local DB — Stock model synced from G-System mes_dev.lg_stock."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Stock(Base):
    """Inventory stock record from G-System lg_stock.

    Synced from GET .../lg/lgstock/aps/pending. able_qty is the key field for
    APS scheduling (available quantity). All qty/amt fields are nullable —
    not all stock types carry every figure.

    G-System's response has TWO distinct ids per row: "id" (the interface
    pending-queue row id — can change across sync cycles for the same stock
    record) and "lgStockId" (the stable business stock-record id). Upserting
    must key off lg_stock_id, not the local PK, to avoid duplicate rows.
    """

    __tablename__ = "aps_stock"
    __table_args__ = {"schema": "aps_input"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # G-System interface pending-queue row id (for traceability only)
    gsystem_if_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    # G-System stable business stock-record id — the real upsert key
    lg_stock_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)

    # Identifiers
    corp_id:     Mapped[str | None] = mapped_column(String(50))
    parea_id:    Mapped[str | None] = mapped_column(String(50))
    biz_id:      Mapped[str | None] = mapped_column(String(50))
    stk_ym:      Mapped[str | None] = mapped_column(String(10), index=True)   # YYYYMM
    stk_type:    Mapped[str | None] = mapped_column(String(20))
    wh_cd:       Mapped[str | None] = mapped_column(String(50), index=True)
    location_id: Mapped[str | None] = mapped_column(String(50))
    # G-System business item id (itemId) — join to aps_item.gsystem_id. Named
    # gsystem_item_id for consistency with aps_mps_plan.gsystem_item_id.
    gsystem_item_id: Mapped[str | None] = mapped_column(String(50), index=True)
    unit_cd:     Mapped[str | None] = mapped_column(String(20))
    lotno:       Mapped[str | None] = mapped_column(String(100))

    # Previous balance
    prev_qty:   Mapped[float | None] = mapped_column(Numeric(18, 4))
    prev_price: Mapped[float | None] = mapped_column(Numeric(18, 4))
    prev_amt:   Mapped[float | None] = mapped_column(Numeric(18, 4))

    # Movement — in
    in_qty:      Mapped[float | None] = mapped_column(Numeric(18, 4))
    buy_qty:     Mapped[float | None] = mapped_column(Numeric(18, 4))
    buy_amt:     Mapped[float | None] = mapped_column(Numeric(18, 4))
    make_qty:    Mapped[float | None] = mapped_column(Numeric(18, 4))
    make_amt:    Mapped[float | None] = mapped_column(Numeric(18, 4))
    etc_in_qty:  Mapped[float | None] = mapped_column(Numeric(18, 4))
    etc_in_amt:  Mapped[float | None] = mapped_column(Numeric(18, 4))
    mv_in_qty:   Mapped[float | None] = mapped_column(Numeric(18, 4))
    mv_in_amt:   Mapped[float | None] = mapped_column(Numeric(18, 4))

    # Movement — out
    out_qty:      Mapped[float | None] = mapped_column(Numeric(18, 4))
    invoice_qty:  Mapped[float | None] = mapped_column(Numeric(18, 4))
    invoice_amt:  Mapped[float | None] = mapped_column(Numeric(18, 4))
    mat_qty:      Mapped[float | None] = mapped_column(Numeric(18, 4))
    mat_amt:      Mapped[float | None] = mapped_column(Numeric(18, 4))
    mv_out_qty:   Mapped[float | None] = mapped_column(Numeric(18, 4))
    mv_out_amt:   Mapped[float | None] = mapped_column(Numeric(18, 4))
    etc_out_qty:  Mapped[float | None] = mapped_column(Numeric(18, 4))
    etc_out_amt:  Mapped[float | None] = mapped_column(Numeric(18, 4))

    # Available quantity — primary field for APS scheduling
    able_qty: Mapped[float | None] = mapped_column(Numeric(18, 4), index=True)

    # Audit
    reg_user_id: Mapped[str | None] = mapped_column(String(50))
    reg_dt:      Mapped[datetime | None] = mapped_column(DateTime)
    reg_ip:      Mapped[str | None] = mapped_column(String(50))
    mod_user_id: Mapped[str | None] = mapped_column(String(50))
    mod_dt:      Mapped[datetime | None] = mapped_column(DateTime)
    mod_ip:      Mapped[str | None] = mapped_column(String(50))

    def __repr__(self) -> str:
        return f"<Stock lg_stock_id={self.lg_stock_id} item={self.gsystem_item_id} ym={self.stk_ym} able={self.able_qty}>"
