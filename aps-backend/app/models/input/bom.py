"""APS Local DB — BOM (Bill of Materials) models."""

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class BOM(Base):
    """BOM header — one per parent item."""

    __tablename__ = "aps_bom"
    __table_args__ = {"schema": "aps_input"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)

    parent_item: Mapped["Item"] = relationship(back_populates="boms")
    components: Mapped[list["BOMComponent"]] = relationship(back_populates="bom")


class BOMComponent(Base):
    """One BOM line (parent → child component)."""

    __tablename__ = "aps_bom_component"
    __table_args__ = {"schema": "aps_input"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bom_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_bom.id"), nullable=False)
    component_item_id: Mapped[int] = mapped_column(ForeignKey("aps_input.aps_item.id"), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4))
    bom_seq: Mapped[int | None] = mapped_column(Integer)

    bom: Mapped["BOM"] = relationship(back_populates="components")
    component_item: Mapped["Item"] = relationship(back_populates="bom_components")
