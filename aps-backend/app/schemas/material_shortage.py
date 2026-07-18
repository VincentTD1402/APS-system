"""Pydantic schemas for the material shortage (자재부족) API."""

from pydantic import BaseModel, Field


class MaterialShortageRebuildResponse(BaseModel):
    """Result of recomputing aps_result.aps_material_shortage."""

    rows_inserted: int = Field(..., description="Component rows written to aps_material_shortage")


class MaterialShortageRow(BaseModel):
    """One (parent product/semiproduct → component) material requirement vs stock."""

    parent_item_id: int | None = Field(None, description="Product/semiproduct (BOM parent) — FK aps_item.id, clickable")
    parent_item_no: str | None = None
    parent_item_name: str | None = None
    item_id: int = Field(..., description="Component/material (BOM child) — FK aps_item.id, clickable")
    item_no: str | None = None
    item_name: str | None = None
    required_qty: float = Field(..., description="Σ plan_qty × qty1/qty2 across MPS lines (소요예정)")
    available_qty: float = Field(..., description="Σ stock in_qty for this component (기초 재고)")
    shortage_qty: float = Field(..., description="max(0, required − available) (자재부족)")
    is_short: bool = Field(..., description="True when shortage_qty > 0")
