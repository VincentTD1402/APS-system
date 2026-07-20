from typing import List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config.config import settings
from app.models import MaterialShortage, WorkCenter
from app.schemas.kpi_summary import (
    DelayedOrderDetail,
    KPI1DeliveryResponse,
    KPI2ShortageResponse,
    KPI3LoadResponse,
    KPI4RiskCountResponse,
    WorkcenterLoadEntry,
    ShortageItemDetail,
)
from app.services.kpi_summary.daily_plan_rollup import workcenter_daily_status_rollup


class KPISummaryService:
    """Service for calculating KPI summaries from plan data."""

    def __init__(self, db: Session, scenario_id: str, run_id: Optional[str] = None):
        self.db = db
        self.scenario_id = scenario_id
        self.run_id = run_id

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

    def calculate_kpi2_shortage(self) -> KPI2ShortageResponse:
        """Read aps_result.aps_material_shortage (call POST /material-shortage/rebuild first).

        Per-component required/available/shortage, BOM-based — not scenario-scoped
        (single G-System snapshot per production area, same as KPI1).
        """
        rows = self.db.execute(
            select(MaterialShortage)
            .where(MaterialShortage.shortage_qty > 0)
            .order_by(MaterialShortage.shortage_qty.desc())
        ).scalars().all()

        shortage_items: List[ShortageItemDetail] = []
        global_total_shortage = 0.0

        for r in rows:
            required_qty = float(r.required_qty or 0)
            available_qty = float(r.available_qty or 0)
            shortage_qty = float(r.shortage_qty or 0)
            shortage_percent = (shortage_qty / required_qty) * 100 if required_qty > 0 else 0.0
            global_total_shortage += shortage_qty

            shortage_items.append(
                ShortageItemDetail(
                    item_id=r.item_id,
                    item_no=r.item_no,
                    item_name=r.item_name,
                    required_qty=round(required_qty, 2),
                    available_qty=round(available_qty, 2),
                    shortage_qty=round(shortage_qty, 2),
                    shortage_percent=round(shortage_percent, 2),
                )
            )

        return KPI2ShortageResponse(
            kpi_value=len(shortage_items),
            total_shortage_qty=round(global_total_shortage, 2),
            items_with_shortage=len(shortage_items),
            risk_triggered=len(shortage_items) > 0,
            shortage_items=shortage_items,
        )

    # ========================================================================
    # KPI 3 – Workcenter Load
    # ========================================================================

    def calculate_kpi3_load(self) -> KPI3LoadResponse:
        """Read aps_result.aps_daily_plan rollup (call POST /kpi-summary/daily-plan/rebuild first).

        kpi_value = % of workcenters (aps_workcenter master) with at least one
        overload/urgent day across the whole rebuilt schedule — matches the FE
        "공정부하율 초과" card (e.g. "5%WC"), not a slot-level average.
        """
        rollup = workcenter_daily_status_rollup(self.db)

        entries: List[WorkcenterLoadEntry] = [
            WorkcenterLoadEntry(
                workcenter_id=r.workcenter_id,
                workcenter_code=r.workcenter_no,
                workcenter_name=r.workcenter_name,
                plan_date=r.work_date,
                total_load_minutes=r.used_minutes,
                capacity_minutes=r.capacity_minutes,
                load_percent=r.load_percent,
                operation_count=0,
                overloaded=r.status in ("overload", "urgent"),
            )
            for r in rollup
        ]
        overloaded_slots = [e for e in entries if e.overloaded]

        if entries:
            avg_load = sum(e.load_percent for e in entries) / len(entries)
            max_load = max(e.load_percent for e in entries)
            min_load = min(e.load_percent for e in entries)
        else:
            avg_load = 0.0
            max_load = 0.0
            min_load = 0.0

        total_wc_count = self.db.execute(select(func.count()).select_from(WorkCenter)).scalar_one()
        overloaded_wc_count = len({r.workcenter_id for r in rollup if r.status in ("overload", "urgent")})
        kpi_value = round(overloaded_wc_count / total_wc_count * 100, 2) if total_wc_count else 0.0

        return KPI3LoadResponse(
            kpi_name="workcenter_load",
            kpi_value=kpi_value,
            overloaded_wc_count=overloaded_wc_count,
            total_wc_count=total_wc_count,
            avg_load=round(avg_load, 2),
            max_load=round(max_load, 2),
            min_load=round(min_load, 2),
            risk_triggered=overloaded_wc_count > 0,
            entries=entries,
            overloaded_slots=overloaded_slots,
        )

    # ========================================================================
    # KPI 4 – Total Risk Count
    # ========================================================================

    def calculate_kpi4_risk_count(self) -> KPI4RiskCountResponse:
        """kpi_value = R1 (delayed orders) + R2 (shortage items) + R3 (overloaded workcenters).

        Reuses KPI1/KPI2/KPI3 as-is — no new query, just sums their counts.
        """
        r1 = self.calculate_kpi1_delivery().delayed_orders
        r2 = self.calculate_kpi2_shortage().items_with_shortage
        r3 = self.calculate_kpi3_load().overloaded_wc_count
        total = r1 + r2 + r3

        return KPI4RiskCountResponse(
            kpi_value=total,
            r1_delayed_orders=r1,
            r2_shortage_items=r2,
            r3_overloaded_wc=r3,
            risk_triggered=total > 0,
        )

