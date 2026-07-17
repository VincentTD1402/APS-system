"""APS Local DB — Material Shortage model.

Computed (not synced) — per raw-material/component the total quantity required
by all MPS plan lines vs the quantity available in stock:

    required  = Σ over MPS lines ( plan_qty × bom.qty1 / bom.qty2 )   # 소요예정
    available = Σ aps_stock.able_qty for that component (기초 재고)
    shortage  = max(0, required − available)                          # 자재부족

Single-version table — rebuilt wholesale on demand
(see material_shortage_builder.rebuild_material_shortage), same pattern as
aps_daily_plan. Direct (1-level) BOM explosion only: the parent item of each
MPS line maps straight to its BOM components; multi-level nesting is ignored.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class MaterialShortage(Base):
    """One component/material's required-vs-available rollup for the current plan."""

    __tablename__ = "aps_material_shortage"
    __table_args__ = ({"schema": "aps_result"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # The component/material item (BOM child).
    item_id: Mapped[int] = mapped_column(
        ForeignKey("aps_input.aps_item.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Denormalized for display (부하내역 / 작업계획 리스트 grids read without a join).
    item_no: Mapped[str | None] = mapped_column(String(50))
    item_name: Mapped[str | None] = mapped_column(String(200))

    required_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    available_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, server_default="0")
    shortage_qty: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, server_default="0", index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    item: Mapped["Item"] = relationship(foreign_keys=[item_id])

    def __repr__(self) -> str:
        return f"<MaterialShortage item={self.item_id} req={self.required_qty} short={self.shortage_qty}>"
