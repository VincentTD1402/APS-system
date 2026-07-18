"""APS Local DB — Material Shortage model.

Computed (not synced) — BOM-like rows (parent product/semiproduct → component)
capturing the material requirement of each MPS production instruction vs stock:

    required  = Σ over MPS lines of THIS parent ( plan_qty × bom.qty1 / bom.qty2 )  # 소요예정
    available = Σ aps_stock.in_qty for the component (기초 재고 / on-hand)
    shortage  = max(0, required − available)                                        # 자재부족

Grain: one row per (parent_item, component_item) — mirrors aps_bom (parent →
component). Both parent_item_id and item_id are FKs to aps_item so the UI can
link/drill like the BOM screen. Single-version: rebuilt wholesale on demand
(see material_shortage_builder.rebuild_material_shortage). Direct (1-level) BOM
explosion only — multi-level nesting is ignored.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MaterialShortage(Base):
    """One (parent product/semiproduct → component) material requirement vs stock."""

    __tablename__ = "aps_material_shortage"
    __table_args__ = ({"schema": "aps_result"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Parent — the product/semiproduct from the MPS instruction (BOM parent). FK → clickable.
    parent_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="CASCADE"), index=True
    )
    parent_item_no: Mapped[str | None] = mapped_column(String(50))
    parent_item_name: Mapped[str | None] = mapped_column(String(200))

    # Component — the required material (BOM child). FK → clickable.
    item_id: Mapped[int] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="CASCADE"), index=True, nullable=False
    )
    item_no: Mapped[str | None] = mapped_column(String(50))
    item_name: Mapped[str | None] = mapped_column(String(200))

    required_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    available_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    shortage_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, server_default="0", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    parent_item: Mapped["Item"] = relationship(foreign_keys=[parent_item_id])
    item: Mapped["Item"] = relationship(foreign_keys=[item_id])

    def __repr__(self) -> str:
        return f"<MaterialShortage parent={self.parent_item_id} item={self.item_id} short={self.shortage_qty}>"
