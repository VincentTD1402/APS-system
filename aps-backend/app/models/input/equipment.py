"""APS Local DB — Equipment model.

Synced from G-System GET /cm/workPlaceEquipmentMng?workshopId={workshopId}.
One workcenter (workshop) has many equipment. Records are time-versioned on
G-System (validFrom/validTo), so the same business equipmentId can appear in
several rows — we keep every version, keyed by the G-System record id.

Key business field: cycle_factor (ST 환산율 / ST conversion rate).
"""

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Equipment(Base):
    """Equipment master per workcenter from G-System cm_workplace_equipment."""

    __tablename__ = "aps_equipment"
    __table_args__ = ({"schema": "aps_input"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # G-System interface record id — unique per validity version (join/upsert key)
    gsystem_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    # G-System business equipmentId (repeats across validity versions)
    equipment_id: Mapped[int | None] = mapped_column(Integer, index=True)
    equipment_name: Mapped[str | None] = mapped_column(String(200))

    # FK to the owning workcenter (resolved from workshopId → WorkCenter.gsystem_id)
    workcenter_id: Mapped[int | None] = mapped_column(
        ForeignKey("aps_input.aps_workcenter.id", ondelete="CASCADE"), index=True
    )
    # Raw G-System workshopId — kept for traceability / re-fetch
    gsystem_workshop_id: Mapped[int | None] = mapped_column(Integer, index=True)

    # ST conversion rate — multiplies workcenter default capacity (std_capa, minutes)
    cycle_factor: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Capacity group (minutes)
    normal_capacity_min: Mapped[int | None] = mapped_column(Integer)
    max_capacity_min: Mapped[int | None] = mapped_column(Integer)
    ot_capacity_min: Mapped[int | None] = mapped_column(Integer)
    holiday_capacity_min: Mapped[int | None] = mapped_column(Integer)

    # Lot group
    min_lot_qty: Mapped[float | None] = mapped_column(Numeric(12, 4))
    max_lot_qty: Mapped[float | None] = mapped_column(Numeric(12, 4))
    concurrent_lot_qty: Mapped[int | None] = mapped_column(Integer)

    # Rate/factor group
    oee_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    efficiency_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    quality_factor: Mapped[float | None] = mapped_column(Numeric(10, 4))
    availability_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))
    assign_rate: Mapped[float | None] = mapped_column(Numeric(10, 4))

    # Scheduling attributes
    priority_order: Mapped[int | None] = mapped_column(Integer)
    required_skill_level: Mapped[str | None] = mapped_column(String(20))
    split_allowed: Mapped[str | None] = mapped_column(String(1))

    # Validity period (G-System YYYYMMDD strings)
    valid_from: Mapped[str | None] = mapped_column(String(8))
    valid_to: Mapped[str | None] = mapped_column(String(8))

    workcenter: Mapped["WorkCenter"] = relationship(back_populates="equipment")

    def __repr__(self) -> str:
        return f"<Equipment {self.equipment_id!r} {self.equipment_name!r} cf={self.cycle_factor}>"
