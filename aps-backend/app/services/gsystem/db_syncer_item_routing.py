"""Item-routing enrichment — backfills workcenter_id/work_time/jph on
aps_item_routing_spec rows that itemRoutingMng left NULL.

`sync_item_routing` (db_syncer.py) reads GET /pd/itemRoutingMng, which names
its workcenter fields "oscustId"/"custNm" (already mapped, not "workcenterId"/
"workcenterNm") but still omits `workTime`/`oscustId` on a large share of the
dev dataset — both resolve to None and jph (3600/work_time) stays NULL too.
This module adds a backfill-only pass using two fallback G-System endpoints:

  1. routingProcessList (fetch_routing_process_list) — keyed by
     (routingId, processId). Carries workcenterId and sometimes
     workTime/setupTime/moveTime. Cached per routing per sync run.
  2. itemProcessListByRouting (fetch_item_process_list_by_routing) — keyed by
     (routingId, itemId, procId). Item-specific workTime fallback, fetched
     lazily only when routingProcessList doesn't supply a work time.

Unit contract: both fallback endpoints report workTime/setupTime/moveTime as
zero-padded MINUTE strings (e.g. "0015" = 15 min). ItemRoutingSpec.work_time
is documented and consumed as SECONDS/EA (jph = 3600 / work_time) — every
value from these endpoints is normalized to seconds via
_parse_gsystem_worktime_to_seconds before being written or used in the jph
formula.

Never overwrites a non-NULL workcenter_id/work_time that itemRoutingMng
already supplied — every write is guarded with `if spec.<field> is None`.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import Item, ItemRoutingSpec, WorkCenter
from app.services.gsystem.db_syncer import _parse_datetime, _to_int

if TYPE_CHECKING:
    from app.services.gsystem.api_client import GSystemClient

logger = get_logger(__name__)

# {gsystem_routing_id: {processId: resolved_record}} — populated lazily,
# scoped to one sync run so a routing shared by many items is fetched once.
RoutingProcessCache = dict[int, dict[int, dict[str, Any]]]
# {(gsystem_routing_id, gsystem_item_id): {procId: record}} — item-level
# fallback, fetched lazily only when routingProcessList lacks a work time.
ItemProcessCache = dict[tuple[int, int], dict[int, dict[str, Any]]]


def _parse_gsystem_worktime_to_seconds(value: Any) -> float | None:
    """Convert a G-System workTime/setupTime/moveTime string (zero-padded
    MINUTES, e.g. "0015", "0030", "0100") to SECONDS, matching
    ItemRoutingSpec.work_time's seconds/EA contract (jph = 3600 / work_time).

    Returns None for empty/None/non-numeric input instead of raising, matching
    the fail-open coercion style of db_syncer._to_int/_to_float.
    """
    if value in (None, ""):
        return None
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        logger.warning("Cannot parse G-System workTime %r as minutes — stored as None", value)
        return None
    return minutes * 60.0


def _resolve_routing_process_rows(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Resolve routingProcessList records to one chosen row per processId.

    routingProcessList can return multiple revision rows sharing the same
    (routingId, processId) — e.g. a thin row created on insert and a richer
    row added by a later edit (workcenterId/workTime populated). The row
    whose modDt (preferred) or regDt is most recent wins; a row with neither
    a parseable modDt nor regDt is treated as lowest priority.
    """
    resolved: dict[int, dict[str, Any]] = {}
    best_ts: dict[int, datetime] = {}
    for rec in records:
        proc_id = rec.get("processId")
        if proc_id is None:
            continue
        pid = int(proc_id)
        ts = _parse_datetime(rec.get("modDt")) or _parse_datetime(rec.get("regDt"))
        current_ts = best_ts.get(pid)
        if pid not in resolved or (ts is not None and (current_ts is None or ts >= current_ts)):
            resolved[pid] = rec
            if ts is not None:
                best_ts[pid] = ts
    return resolved


def _get_or_fetch_routing_process(
    client: "GSystemClient",
    routing_process_cache: RoutingProcessCache,
    gsys_routing_id: int,
) -> dict[int, dict[str, Any]]:
    """Return {processId: resolved_record} for a routing, fetching + resolving
    once per sync run (fail-open — network errors leave the routing's entry
    empty so callers simply find no match)."""
    if gsys_routing_id in routing_process_cache:
        return routing_process_cache[gsys_routing_id]
    try:
        records = client.fetch_routing_process_list(gsys_routing_id)
    except Exception as exc:
        logger.warning("fetch_routing_process_list failed for routingId=%s: %s", gsys_routing_id, exc)
        records = []
    resolved = _resolve_routing_process_rows(records)
    routing_process_cache[gsys_routing_id] = resolved
    return resolved


def _get_or_fetch_item_process(
    client: "GSystemClient",
    item_proc_cache: ItemProcessCache,
    gsys_routing_id: int,
    gsys_item_id: int,
) -> dict[int, dict[str, Any]]:
    """Return {procId: record} for one (routing, item) pair, fetched lazily
    and cached — only called when routingProcessList didn't supply workTime."""
    key = (gsys_routing_id, gsys_item_id)
    if key in item_proc_cache:
        return item_proc_cache[key]
    try:
        records = client.fetch_item_process_list_by_routing(gsys_routing_id, gsys_item_id)
    except Exception as exc:
        logger.warning(
            "fetch_item_process_list_by_routing failed routingId=%s itemId=%s: %s",
            gsys_routing_id, gsys_item_id, exc,
        )
        records = []
    index = {int(r["procId"]): r for r in records if r.get("procId") is not None}
    item_proc_cache[key] = index
    return index


def enrich_item_routing_specs(
    session: Session,
    item: Item,
    client: "GSystemClient",
    routing_process_cache: RoutingProcessCache,
    item_proc_cache: ItemProcessCache | None = None,
) -> int:
    """Backfill workcenter_id/work_time/jph on this item's ItemRoutingSpec rows
    still missing them after sync_item_routing. Backfill-only: never touches a
    row whose workcenter_id/work_time is already non-NULL. Returns rows changed.
    """
    if item_proc_cache is None:
        item_proc_cache = {}

    specs = session.execute(
        select(ItemRoutingSpec).where(
            ItemRoutingSpec.item_id == item.id,
            ItemRoutingSpec.gsystem_routing_id.isnot(None),
            or_(ItemRoutingSpec.workcenter_id.is_(None), ItemRoutingSpec.work_time.is_(None)),
        )
    ).scalars().all()
    if not specs:
        return 0

    enriched = 0
    for spec in specs:
        gsys_routing_id = int(spec.gsystem_routing_id)
        resolved = _get_or_fetch_routing_process(client, routing_process_cache, gsys_routing_id)
        rec = resolved.get(spec.gsystem_proc_id) if spec.gsystem_proc_id is not None else None
        changed = False

        if spec.workcenter_id is None and rec is not None:
            wc_gsys_id = _to_int(rec.get("workcenterId"))
            if wc_gsys_id is not None:
                spec.gsystem_workcenter_id = wc_gsys_id
                wc = session.execute(
                    select(WorkCenter).where(WorkCenter.gsystem_id == wc_gsys_id)
                ).scalar_one_or_none()
                if wc is not None:
                    spec.workcenter_id = wc.id
                changed = True

        if spec.work_time is None:
            work_time = _parse_gsystem_worktime_to_seconds(rec.get("workTime")) if rec else None
            if work_time is None and item.gsystem_id is not None:
                ip_index = _get_or_fetch_item_process(
                    client, item_proc_cache, gsys_routing_id, int(item.gsystem_id)
                )
                ip_rec = ip_index.get(spec.gsystem_proc_id) if spec.gsystem_proc_id is not None else None
                if ip_rec is not None:
                    work_time = _parse_gsystem_worktime_to_seconds(ip_rec.get("workTime"))
            if work_time is not None and work_time > 0:
                spec.work_time = work_time
                spec.jph = round(3600.0 / work_time, 2)
                changed = True

        if changed:
            enriched += 1

    if enriched:
        session.flush()
    logger.info("enrich_item_routing_specs: item_id=%s %d rows enriched", item.id, enriched)
    return enriched
