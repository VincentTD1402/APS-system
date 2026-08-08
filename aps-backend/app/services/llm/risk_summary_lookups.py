"""Shared lookups for the plan-wide risk summary builders."""
from __future__ import annotations

from datetime import date as date_cls, datetime, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_logger, settings
from app.models import WorkOrder
from app.schemas.work_plan import WorkPlanRow

logger = get_logger(__name__)

_tz_cache: tzinfo | None = None


def _calendar_tz() -> tzinfo:
    """Plant calendar timezone, resolved once.

    UTC is handled without ZoneInfo so the default setting works on hosts with
    no IANA tz database (Windows without `tzdata`). An unresolvable name warns
    once and degrades to UTC rather than shifting dates silently.
    """
    global _tz_cache
    if _tz_cache is None:
        name = (settings.APS_CALENDAR_TIMEZONE or "UTC").strip()
        if name.upper() == "UTC":
            _tz_cache = timezone.utc
        else:
            try:
                _tz_cache = ZoneInfo(name)
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning("Unknown APS_CALENDAR_TIMEZONE=%s — using UTC", name)
                _tz_cache = timezone.utc
    return _tz_cache


def today_in_calendar_tz() -> date_cls:
    """Today in the plant's calendar timezone (APS_CALENDAR_TIMEZONE)."""
    return datetime.now(_calendar_tz()).date()


def days_from_today(target: date_cls | None) -> int | None:
    """Signed day delta from today; negative means the date has passed."""
    if target is None:
        return None
    return (target - today_in_calendar_tz()).days


def plan_window(rows: list[WorkPlanRow]) -> tuple[date_cls | None, date_cls | None]:
    """Earliest/latest day the listed plans occupy.

    Built from each row's own aps_daily_plan days, falling back to its
    plan_start/plan_end when the row has no daily breakdown yet.
    """
    days: list[date_cls] = []
    for row in rows:
        if row.daily_plans:
            days.extend(e.date for e in row.daily_plans)
        else:
            days.extend(d for d in (row.plan_start, row.plan_end) if d is not None)
    return (min(days), max(days)) if days else (None, None)


def mps_ids_by_row(db: Session, rows: list[WorkPlanRow]) -> dict[str, int]:
    """work_order.id (the FE row key) → mps_plan_id, for the listed rows only."""
    wo_ids: list[int] = []
    for row in rows:
        try:
            wo_ids.append(int(row.id))
        except ValueError:
            continue
    if not wo_ids:
        return {}
    pairs = db.execute(
        select(WorkOrder.id, WorkOrder.mps_plan_id).where(WorkOrder.id.in_(wo_ids))
    ).all()
    return {str(wid): mps_id for wid, mps_id in pairs if mps_id is not None}
