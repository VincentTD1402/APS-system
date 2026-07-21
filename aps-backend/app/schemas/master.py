"""Master data schemas for the FE master views (work-centers, items, routings,
BOM, inventory). Fields are snake_case in Python but serialized as camelCase to
match the FE contract (e.g. wcCode, nameKo, defaultRuntimeMin)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base that serializes snake_case fields as camelCase for the FE."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EquipmentOut(CamelModel):
    code: str = Field(..., description="Equipment id (aps_equipment.equipment_id)")
    wc_code: str | None = Field(None, description="Parent workcenter_no")
    name_ko: str | None = Field(None, description="aps_equipment.equipment_name")
    st_rate: float | None = Field(None, description="Standard rate = cycle_factor")


class WorkCenterOut(CamelModel):
    code: str = Field(..., description="aps_workcenter.workcenter_no")
    name_ko: str | None = Field(None, description="aps_workcenter.workcenter_name")
    default_runtime_min: float | None = Field(None, description="std_capa (minutes/day)")
    total_runtime_min: float | None = Field(
        None, description="std_capa × number of equipment on the workcenter"
    )
    equipments: list[EquipmentOut] = Field(default_factory=list)


class ItemOut(CamelModel):
    code: str = Field(..., description="aps_item.item_no")
    name_ko: str | None = Field(None, description="aps_item.item_name")
    uom: str | None = Field(None, description="Unit of measure (aps_item.uom, default EA)")


class RoutingOut(CamelModel):
    id: int
    item_code: str | None = Field(None, description="Item's item_no")
    step_no: int | None = Field(None, description="aps_item_routing_spec.proc_sno")
    wc_code: str | None = Field(None, description="Workcenter's workcenter_no")
    process_name_ko: str | None = Field(None, description="proc_name")
    standard_st_min: float | None = Field(None, description="Standard time per unit in MINUTES (BE stores work_time as seconds; route divides by 60)")


class BomComponentOut(CamelModel):
    id: int
    parent_item_code: str | None = Field(None, description="Parent item_no")
    child_item_code: str | None = Field(None, description="Component item_no")
    qty_per: float | None = Field(None, description="Effective per-unit qty = qty1 / qty2")
    scrap_rate: float | None = Field(None, description="Scrap/loss rate (0 = none)")


class InventoryRowOut(CamelModel):
    id: int
    item_code: str | None = Field(None, description="Item's item_no (resolved via gsystem_item_id)")
    warehouse_code: str | None = Field(None, description="aps_stock.wh_cd")
    on_hand: float | None = Field(None, description="Available stock qty (aps_stock.able_qty) — not in_qty which is inbound-in-period")
    as_of_date: str | None = Field(None, description="stk_ym (YYYYMM) → YYYY-MM-01")
