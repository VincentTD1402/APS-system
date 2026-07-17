"""APS Local DB — Item model."""

from typing import List
from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Item(Base):
    """Normalized item/product master from G-System cm_item."""

    __tablename__ = "aps_item"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('Product','SemiProduct','RawMaterial')",
            name="ck_item_asset_type",
        ),
        {"schema": "aps_input"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Business key from G-System (item_no); must be unique across APS
    item_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    # Original G-System integer itemId — used as join key for routing/BOM APIs
    gsystem_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    item_name: Mapped[str | None] = mapped_column(String(200))
    # "Product" | "SemiProduct" | "RawMaterial"
    asset_type: Mapped[str | None] = mapped_column(String(20))
    spec: Mapped[str | None] = mapped_column(String(200))

    demands: Mapped[List["Demand"]] = relationship(back_populates="item")
    bom_parent_links: Mapped[List["BOM"]] = relationship(
        back_populates="parent_item", foreign_keys="BOM.parent_item_id"
    )
    bom_component_links: Mapped[List["BOM"]] = relationship(
        back_populates="component_item", foreign_keys="BOM.component_item_id"
    )
    plan_shortages: Mapped[List["PlanShortage"]] = relationship(back_populates="item")
    routing_items: Mapped[list["RoutingItem"]] = relationship(back_populates="item")
    item_process_steps: Mapped[list["ItemProcessStep"]] = relationship(back_populates="item")

    def __repr__(self) -> str:
        return f"<Item {self.item_no!r} {self.item_name!r}>"
