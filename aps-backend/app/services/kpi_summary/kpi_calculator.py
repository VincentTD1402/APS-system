import re
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.config import settings
from app.schemas.kpi_summary import (
    DelayedOrderDetail,
    KPI1DeliveryResponse,
    KPI2ShortageResponse,
    KPI3LoadResponse,
    WorkcenterLoadEntry,
    ShortageItemDetail,
)


class KPISummaryService:
    """Service for calculating KPI summaries from plan data."""

    def __init__(self, db: Session, scenario_id: str, run_id: Optional[str] = None):
        self.db = db
        self.scenario_id = scenario_id
        self.run_id = run_id

    def _resolve_parent_scenario_id(self, scenario_id: Optional[str] = None) -> Optional[str]:
        """Baseline id for a simulation branch (DB FK or SCH-Rx_sim_N pattern)."""
        sid = scenario_id or self.scenario_id
        row = self.db.execute(
            text(
                "SELECT parent_scenario_id FROM aps_result.plan_scenario WHERE scenario_id = :sid"
            ),
            {"sid": sid},
        ).fetchone()
        if row is not None:
            pid = row._mapping.get("parent_scenario_id")
            if pid:
                return str(pid)
        m = re.match(r"^(.*)_sim_[123]$", sid)
        return m.group(1) if m else None

    # ========================================================================
    # KPI 1 – Delivery Compliance Rate
    # ========================================================================

    def calculate_kpi1_delivery(self, scenario_id: Optional[str] = None) -> KPI1DeliveryResponse:
        """Compliance = aps_mps_plan.plan_end_date <= delivery_date, per MPS line.

        Sourced from aps_mps_plan (G-System MPS, synced via prodPlanMpsMng) rather
        than aps_result.plan_order — MPS already carries both delivery_date and
        plan_end_date, so no APS scheduling run is required to compute this KPI.
        Not scenario-scoped: aps_mps_plan has no scenario_id (single G-System
        snapshot per production area), so `scenario_id` is accepted for interface
        compatibility but unused here.
        """
        query = text(
            """
            SELECT
                mp.gsystem_id,
                mp.plan_no,
                i.item_no,
                i.item_name,
                mp.plan_end_date,
                mp.delivery_date,
                mp.status_cd
            FROM aps_input.aps_mps_plan mp
            LEFT JOIN aps_input.aps_item i ON mp.item_id = i.id
            WHERE mp.delivery_date IS NOT NULL AND mp.plan_end_date IS NOT NULL
            ORDER BY mp.plan_end_date
            """
        )

        rows = self.db.execute(query).fetchall()

        total_orders = len(rows)
        on_time_orders = 0
        delayed_orders = 0
        delayed_order_details: List[DelayedOrderDetail] = []

        for row in rows:
            m = row._mapping
            plan_id = str(m["gsystem_id"])
            plan_no = m["plan_no"]
            item_no = m["item_no"]
            item_name = m["item_name"]
            plan_end_date = m["plan_end_date"]
            delivery_date = m["delivery_date"]
            late_days = max(0, (plan_end_date - delivery_date).days)
            plan_status = m["status_cd"]

            if late_days > 0:
                delayed_orders += 1
                delayed_order_details.append(
                    DelayedOrderDetail(
                        plan_id=plan_id,
                        demand_id=None,
                        plan_no=plan_no,
                        item_no=item_no,
                        item_name=item_name,
                        planned_ship_date=plan_end_date,
                        delivery_date=delivery_date,
                        delay_days=late_days,
                        plan_status=plan_status,
                    )
                )

        if total_orders > 0:
            on_time_orders = total_orders - delayed_orders
            compliance_rate = (on_time_orders / total_orders) * 100.0
        else:
            on_time_orders = 0
            compliance_rate = 100.0

        # R1 risk triggered if compliance rate < threshold
        risk_triggered = compliance_rate < settings.KPI_R1_COMPLIANCE_THRESHOLD

        return KPI1DeliveryResponse(
            kpi_value=round(compliance_rate, 2),
            total_orders=total_orders,
            on_time_orders=on_time_orders,
            delayed_orders=delayed_orders,
            risk_triggered=risk_triggered,
            delayed_order_details=delayed_order_details,
        )

    # ========================================================================
    # KPI 2 – Material Shortage
    # ========================================================================

    def calculate_kpi2_shortage(self, scenario_id: Optional[str] = None) -> KPI2ShortageResponse:
        sid = scenario_id or self.scenario_id
        query = text(
            """
                SELECT
                    ps.item_id,
                    i.item_no,
                    i.item_name,
                    SUM(ps.required_qty) AS total_required,
                    SUM(ps.available_qty) AS total_available,
                    SUM(GREATEST(0, ps.required_qty - ps.available_qty)) AS calculated_shortage
                FROM aps_result.plan_shortage ps
                LEFT JOIN aps_input.aps_item i ON ps.item_id = i.id
                WHERE ps.scenario_id = :scenario_id
                GROUP BY ps.item_id, i.item_no, i.item_name
                HAVING SUM(GREATEST(0, ps.required_qty - ps.available_qty)) > 0
                ORDER BY calculated_shortage DESC
                """
        )

        rows = self.db.execute(
            query, {"scenario_id": sid}).fetchall()

        shortage_items: List[ShortageItemDetail] = []
        global_total_shortage = 0.0

        for row in rows:
            m = row._mapping
            item_id = m["item_id"]
            item_no = m["item_no"]
            item_name = m["item_name"]
            required_qty = float(m["total_required"]) if m["total_required"] else 0.0
            available_qty = float(m["total_available"]) if m["total_available"] else 0.0
            shortage_qty = float(m["calculated_shortage"]) if m["calculated_shortage"] else 0.0

            if required_qty > 0:
                shortage_percent = (shortage_qty / required_qty) * 100
            else:
                shortage_percent = 0.0

            global_total_shortage += shortage_qty

            shortage_items.append(
                ShortageItemDetail(
                    item_id=item_id,
                    item_no=item_no,
                    item_name=item_name,
                    required_qty=round(required_qty, 2),
                    available_qty=round(available_qty, 2),
                    shortage_qty=round(shortage_qty, 2),
                    shortage_percent=round(shortage_percent, 2),
                )
            )

        risk_triggered = global_total_shortage > 0

        return KPI2ShortageResponse(
            kpi_value=round(global_total_shortage, 2),
            total_shortage_qty=round(global_total_shortage, 2),
            items_with_shortage=len(shortage_items),
            risk_triggered=risk_triggered,
            shortage_items=shortage_items,
        )

    # ========================================================================
    # KPI 3 – Workcenter Load
    # ========================================================================

    def _entries_from_plan_utilization(
        self, scenario_id: str
    ) -> Tuple[List[WorkcenterLoadEntry], List[WorkcenterLoadEntry]]:
        query = text(
            """
                SELECT
                    pu.workcenter_id,
                    wc.workcenter_no,
                    wc.workcenter_name,
                    pu.plan_date,
                    pu.used_capacity,
                    pu.available_capacity,
                    pu.utilization_rate
                FROM aps_result.plan_utilization pu
                LEFT JOIN aps_input.aps_workcenter wc ON pu.workcenter_id = wc.id
                WHERE pu.scenario_id = :scenario_id
                ORDER BY wc.workcenter_no, pu.plan_date
                """
        )

        rows = self.db.execute(
            query, {"scenario_id": scenario_id}).fetchall()

        entries: List[WorkcenterLoadEntry] = []
        overloaded_slots: List[WorkcenterLoadEntry] = []

        for row in rows:
            m = row._mapping
            workcenter_id = m["workcenter_id"]
            workcenter_code = m["workcenter_no"]
            workcenter_name = m["workcenter_name"]
            plan_date = m["plan_date"]

            used_capacity = float(m["used_capacity"]) if m["used_capacity"] else 0.0
            available_capacity = float(m["available_capacity"]) if m["available_capacity"] else 0.0

            if m["utilization_rate"] is not None:
                load_percent = float(m["utilization_rate"])
            elif available_capacity > 0:
                load_percent = (used_capacity / available_capacity) * 100.0
            else:
                load_percent = 999.99 if used_capacity > 0 else 0.0

            overloaded = load_percent > settings.KPI_R3_OVERLOAD_THRESHOLD

            entry = WorkcenterLoadEntry(
                workcenter_id=workcenter_id,
                workcenter_code=workcenter_code,
                workcenter_name=workcenter_name,
                plan_date=plan_date,
                total_load_minutes=round(used_capacity, 2),
                capacity_minutes=round(available_capacity, 2),
                load_percent=round(load_percent, 2),
                operation_count=0,
                overloaded=overloaded,
            )

            entries.append(entry)
            if overloaded:
                overloaded_slots.append(entry)

        return entries, overloaded_slots

    def _entries_from_workcenter_load(
        self, scenario_id: str
    ) -> Tuple[List[WorkcenterLoadEntry], List[WorkcenterLoadEntry]]:
        """Fallback when plan_utilization is empty (common on simulation branches)."""
        query = text(
            """
                SELECT
                    wl.workcenter_id,
                    wc.workcenter_no,
                    wc.workcenter_name,
                    wl.work_date,
                    wl.used_minutes,
                    wl.capacity_minutes,
                    wl.load_percent,
                    wl.overloaded
                FROM aps_result.workcenter_load wl
                LEFT JOIN aps_input.aps_workcenter wc ON wl.workcenter_id = wc.id
                WHERE wl.scenario_id = :scenario_id
                ORDER BY wc.workcenter_no, wl.work_date
                """
        )
        rows = self.db.execute(
            query, {"scenario_id": scenario_id}).fetchall()
        entries: List[WorkcenterLoadEntry] = []
        overloaded_slots: List[WorkcenterLoadEntry] = []

        for row in rows:
            m = row._mapping
            used_m = float(m["used_minutes"]) if m["used_minutes"] else 0.0
            cap_m = float(m["capacity_minutes"]) if m["capacity_minutes"] else 0.0
            load_percent = float(m["load_percent"]) if m["load_percent"] is not None else 0.0
            overloaded_flag = bool(m["overloaded"]) if m["overloaded"] is not None else False
            overloaded = overloaded_flag or load_percent > settings.KPI_R3_OVERLOAD_THRESHOLD

            entry = WorkcenterLoadEntry(
                workcenter_id=m["workcenter_id"],
                workcenter_code=m["workcenter_no"],
                workcenter_name=m["workcenter_name"],
                plan_date=m["work_date"],
                total_load_minutes=round(used_m, 2),
                capacity_minutes=round(cap_m, 2),
                load_percent=round(load_percent, 2),
                operation_count=0,
                overloaded=overloaded,
            )
            entries.append(entry)
            if overloaded:
                overloaded_slots.append(entry)

        return entries, overloaded_slots

    def calculate_kpi3_load(self, scenario_id: Optional[str] = None) -> KPI3LoadResponse:
        """Load KPI from plan_utilization, then workcenter_load, then parent baseline."""
        sid = scenario_id or self.scenario_id

        entries, overloaded_slots = self._entries_from_plan_utilization(sid)
        if not entries:
            entries, overloaded_slots = self._entries_from_workcenter_load(sid)

        parent = self._resolve_parent_scenario_id(sid)
        if not entries and parent:
            entries, overloaded_slots = self._entries_from_plan_utilization(parent)
            if not entries:
                entries, overloaded_slots = self._entries_from_workcenter_load(parent)

        if entries:
            avg_load = sum(e.load_percent for e in entries) / len(entries)
            max_load = max(e.load_percent for e in entries)
            min_load = min(e.load_percent for e in entries)
        else:
            avg_load = 0.0
            max_load = 0.0
            min_load = 0.0

        risk_triggered = bool(overloaded_slots)

        return KPI3LoadResponse(
            kpi_name="workcenter_load",
            avg_load=round(avg_load, 2),
            max_load=round(max_load, 2),
            min_load=round(min_load, 2),
            risk_triggered=risk_triggered,
            entries=entries,
            overloaded_slots=overloaded_slots,
        )

