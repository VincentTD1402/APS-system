"""KPI Summary Schemas - Pydantic models for KPI summary API responses."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import List, Optional


# ============================================================================
# KPI 1 – Delivery Compliance Rate
# ============================================================================

class DelayedOrderDetail(BaseModel):
    """Detail of a single delayed order for R1 risk."""
    plan_id: str = Field(..., description="Plan order ID")
    demand_id: Optional[int] = Field(None, description="Demand ID")
    plan_no: Optional[str] = Field(None, description="Demand plan number")
    item_no: Optional[str] = Field(None, description="Item code")
    item_name: Optional[str] = Field(None, description="Item name")
    planned_ship_date: Optional[date] = Field(None, description="Planned shipment date from plan")
    delivery_date: Optional[date] = Field(None, description="Required delivery date from demand")
    delay_days: int = Field(0, description="Number of days delayed (positive = late)")
    plan_status: Optional[str] = Field(None, description="Current plan status")


class KPI1DeliveryResponse(BaseModel):
    """KPI 1 – Delivery Compliance Rate response."""
    kpi_name: str = Field("delivery_compliance_rate", description="KPI name")
    kpi_value: float = Field(..., ge=0.0, le=100.0, description="Compliance rate percentage (0-100)")
    total_orders: int = Field(..., description="Total number of orders in scenario")
    on_time_orders: int = Field(..., description="Number of on-time orders")
    delayed_orders: int = Field(..., description="Number of delayed orders")
    risk_triggered: bool = Field(..., description="Whether R1 risk is triggered (rate < 100%)")
    delayed_order_details: List[DelayedOrderDetail] = Field(
        default_factory=list,
        description="List of delayed order details"
    )


# ============================================================================
# KPI 2 – Material Shortage
# ============================================================================

class ShortageItemDetail(BaseModel):
    """Detail of a single material shortage."""
    item_id: Optional[int] = Field(None, description="Item ID")
    item_no: Optional[str] = Field(None, description="Item code")
    item_name: Optional[str] = Field(None, description="Item name")
    required_qty: float = Field(..., description="Required quantity")
    available_qty: float = Field(..., description="Available quantity")
    shortage_qty: float = Field(..., description="Shortage quantity (required - available)")
    shortage_percent: float = Field(..., description="Shortage percentage")


class KPI2ShortageResponse(BaseModel):
    """KPI 2 – Material Shortage response."""
    kpi_name: str = Field("material_shortage", description="KPI name")
    kpi_value: float = Field(..., description="Total shortage quantity")
    total_shortage_qty: float = Field(..., description="Total shortage quantity across all items")
    items_with_shortage: int = Field(..., description="Number of items with shortage")
    risk_triggered: bool = Field(..., description="Whether R2 risk is triggered (any shortage > 0)")
    shortage_items: List[ShortageItemDetail] = Field(
        default_factory=list,
        description="List of shortage item details"
    )


# ============================================================================
# KPI 3 – Workcenter Load
# ============================================================================

class WorkcenterLoadLineItem(BaseModel):
    """One snapshot row from `workcenter_load` (under a workcenter group)."""

    load_id: str
    scenario_id: str
    run_id: Optional[str] = None
    work_date: date
    operation_id: Optional[int] = None
    proc_name: Optional[str] = None
    used_minutes: float
    capacity_minutes: float
    load_percent: float
    overloaded: bool
    status: str
    created_at: datetime


class WorkcenterLoadByWorkcenter(BaseModel):
    """Grouped load data: workcenter identity + nested rows from `workcenter_load`."""

    workcenter_name: Optional[str] = Field(None, description="From aps_workcenter.workcenter_name")
    wc_id: int = Field(..., description="Workcenter PK — same as aps_workcenter.id")
    workcenter_no: Optional[str] = Field(None, description="From aps_workcenter.workcenter_no")
    loads: List[WorkcenterLoadLineItem] = Field(
        default_factory=list,
        description="Load snapshots for this workcenter (dates / overload / status / …)",
    )


class WorkcenterLoadEntry(BaseModel):
    """Single workcenter load entry for a specific date."""
    workcenter_id: int = Field(..., description="Workcenter ID")
    workcenter_code: Optional[str] = Field(None, description="Workcenter code")
    workcenter_name: Optional[str] = Field(None, description="Workcenter name")
    plan_date: date = Field(..., description="Plan date")
    total_load_minutes: float = Field(..., description="Total load in minutes")
    capacity_minutes: float = Field(..., description="Available capacity in minutes (8 hours = 480)")
    load_percent: float = Field(..., description="Load percentage")
    operation_count: int = Field(..., description="Number of operations scheduled")
    overloaded: bool = Field(..., description="Whether load exceeds 100%")


class KPI3LoadResponse(BaseModel):
    """KPI 3 – Workcenter Load response."""
    kpi_name: str = Field("workcenter_load", description="KPI name")
    avg_load: float = Field(..., description="Average load percentage across all entries")
    max_load: float = Field(..., description="Maximum load percentage")
    min_load: float = Field(..., description="Minimum load percentage")
    risk_triggered: bool = Field(..., description="Whether R3 risk is triggered (any load > 100%)")
    entries: List[WorkcenterLoadEntry] = Field(
        default_factory=list,
        description="List of workcenter load entries"
    )
    overloaded_slots: List[WorkcenterLoadEntry] = Field(
        default_factory=list,
        description="List of overloaded workcenter slots"
    )



# ============================================================================
# Plan impacted orders (DB)
# ============================================================================

class PlanImpactedOrderRow(BaseModel):
    """One row from `aps_result.plan_impacted_order`."""

    impacted_id: str = Field(..., description="Primary key — impacted record id")
    scenario_id: str
    plan_id: str
    run_id: Optional[str] = None
    demand_id: Optional[int] = None
    reason_type: str
    planned_start_date: Optional[date] = Field(
        None, description="Planned start date from aps_result.plan_order"
    )
    planned_ship_date: Optional[date] = Field(
        None, description="Planned shipment date from aps_result.plan_order"
    )
    planned_finish_date: Optional[date] = Field(
        None, description="Planned finish date from aps_result.plan_order"
    )
    late_days: Optional[int] = Field(
        None, description="Late days from aps_result.plan_order"
    )
    priority_score: Optional[float] = Field(
        None, description="Priority score from aps_result.plan_order"
    )
    workcenter_ids: List[int] = Field(
        default_factory=list,
        description="Distinct workcenter IDs handling this plan/order",
    )
    workcenter_names: List[str] = Field(
        default_factory=list,
        description="Distinct workcenter names handling this plan/order",
    )
    message: Optional[str] = None
    created_at: datetime


# ============================================================================
# Request/Response Helpers
# ============================================================================

class ScenarioRequest(BaseModel):
    """Request body for KPI summary endpoints."""
    scenario_id: str = Field(..., description="Scenario ID")


class KPIStatusResponse(BaseModel):
    """Simple status response for KPI computation."""
    scenario_id: str
    status: str = Field(..., description="Status (PENDING, COMPUTING, COMPLETED, FAILED)")
    message: Optional[str] = Field(None, description="Status message")
    computed_at: Optional[datetime] = Field(None, description="Computation timestamp")


# ============================================================================
# Daily Plan (backward-fill) — standalone, not KPI3
# ============================================================================

class DailyPlanRow(BaseModel):
    """One row from aps_result.aps_daily_plan."""
    work_date: date
    workcenter_id: int
    workcenter_no: Optional[str] = None
    workcenter_name: Optional[str] = None
    planned_qty: float
    proc_sno: Optional[int] = None
    proc_name: Optional[str] = None
    plan_no: Optional[str] = None
    item_no: Optional[str] = None
    status: str = Field(
        "normal",
        description="'overload' when required minutes for (workcenter, work_date) exceed capacity, else 'normal'",
    )


class WorkcenterDailyStatus(BaseModel):
    """Workcenter-level rollup of aps_daily_plan for one (workcenter, work_date) — no item breakdown."""
    work_date: date
    workcenter_id: int
    workcenter_no: Optional[str] = None
    workcenter_name: Optional[str] = None
    planned_qty_total: float = Field(..., description="Sum of planned_qty assigned to this workcenter/day")
    daily_out_qty: float = Field(
        ..., description="Max producible qty/day = (std_capa × Σcycle_factor) / work_time(min)"
    )
    used_minutes: float
    capacity_minutes: float
    load_percent: float
    status: str = Field("normal", description="'overload' when planned_qty_total > daily_out_qty, else 'normal'")


class DailyPlanRebuildResponse(BaseModel):
    """Result of recomputing aps_result.aps_daily_plan."""
    rows_inserted: int = Field(..., description="Rows written to aps_daily_plan")
    daily_status: List[WorkcenterDailyStatus] = Field(
        default_factory=list,
        description="Per-(workcenter, work_date) load rollup of the rows just rebuilt "
                    "(same shape as GET /daily-plan/workcenter-status).",
    )