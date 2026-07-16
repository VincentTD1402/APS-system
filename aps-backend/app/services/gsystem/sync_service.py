"""G-System sync service — Phase 01 only (fetch → DB → push confirmation + calendar).

Used by the API route POST /sync/run so the pipeline script and the HTTP endpoint
share the same sync logic without duplication.

Sync has two phases:
  1. Pending sync — fetch delta records (ifRecvYn=false), sync to DB, push confirmation
  2. By-routing enrichment — for each routing in the batch, call routingItemList +
     itemProcessListByRouting to populate work_time_hours on aps_item_process_step
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from sqlalchemy import select

logger = logging.getLogger(__name__)

# Keys that require a non-null business ID before push confirmation.
# Orphaned records (e.g. routing deleted on G-System side) are skipped
# so they stay in G-System pending queue until the G-System team cleans them up.
_PUSH_REQUIRED_FIELD: dict[str, str] = {
    "items":             "itemId",
    "workcenters":       "workshopId",
    "routings":          "routingId",
    "routing_items":     "routingId",
    "routing_processes": "routingId",
    "bom":               "upitemId",
    "prod_plans":        "planNo",
    "item_processes":    "itemId",
}

_PUSH_ORDER: list[tuple[str, str]] = [
    ("item",            "items"),
    ("workshop",        "workcenters"),
    ("process",         "processes"),
    ("routing",         "routings"),
    ("routing_item",    "routing_items"),
    ("routing_process", "routing_processes"),
    ("bom",             "bom"),
    ("prod_plan",       "prod_plans"),
    ("item_process",    "item_processes"),
    ("calendar",        "calendar"),
    ("stock",           "stock"),
    ("customer",        "customers"),
]


@dataclass
class SyncResult:
    """Summary returned after a sync run."""
    started_at: datetime
    finished_at: datetime | None = None
    success: bool = False
    error: str | None = None
    # Per-entity counts {entity: {"synced": n, "skipped": n}}
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    calendar_synced: int = 0
    stock_synced: int = 0
    item_processes_enriched: int = 0  # rows enriched via by-routing APIs
    equipment_synced: int = 0  # rows synced via workPlaceEquipmentMng (by-workshop)
    mps_plan_synced: int = 0  # rows synced via prodPlanMpsMng (by-pareaId)
    item_routing_synced: int = 0  # rows synced via itemRoutingMng (by-item x itemRev)
    # Neo4j import stats (Phase 02-04) — disabled, nothing reads the graph anymore
    # neo4j_nodes: int = 0
    # neo4j_relationships: int = 0
    # rdf_triples: int = 0
    # neo4j_skipped: bool = False  # True if Neo4j not configured


def run_gsystem_sync() -> SyncResult:
    """Fetch pending records from G-System, sync to APS DB, push confirmation.

    After pending sync, runs by-routing enrichment for all routings in the batch
    to populate work_time_hours on aps_item_process_step.

    Returns a SyncResult with counts and status.
    Raises no exceptions — errors are captured in SyncResult.error.
    """
    from app.config import settings
    from app.db.database import SessionLocal
    from app.services.gsystem.api_client import GSystemClient, GSystemConfig
    from app.services.gsystem.db_syncer import sync_all

    result = SyncResult(started_at=datetime.now(timezone.utc))

    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_BASE_URL,
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
        all_data=settings.GSYSTEM_ALL_DATA,
    )

    try:
        with GSystemClient(cfg) as client:
            data = client.fetch_all()
            _enrich_prod_plans_with_customer(data["prod_plans"], settings)

            with SessionLocal() as session:
                sync_all(session, data)
                session.commit()

            # Push confirmation — skip orphaned records
            for entity, key in _PUSH_ORDER:
                req_field = _PUSH_REQUIRED_FIELD.get(key)
                all_records = data.get(key, [])
                records = (
                    [r for r in all_records if r.get(req_field) is not None]
                    if req_field else all_records
                )
                skipped = len(all_records) - len(records)
                if skipped:
                    logger.warning(
                        "push %s: skipped %d orphaned records (null %s)",
                        entity, skipped, req_field,
                    )
                client.push(entity, records)
                result.counts[entity] = {"synced": len(records), "skipped": skipped}

            # Phase 2: enrich item_processes with work_time_hours via by-routing APIs
            routing_gsys_ids = {
                int(r["routingId"])
                for r in data.get("routings", [])
                if r.get("routingId") is not None and r.get("ifStatus") != "D"
            }
            if routing_gsys_ids:
                result.item_processes_enriched = _enrich_item_processes(client, routing_gsys_ids)

            # Phase 3: sync equipment per workcenter via workPlaceEquipmentMng (GET by workshopId)
            result.equipment_synced = _enrich_equipment(client)

            # Phase 4: sync MPS plan (by pareaId) + item routing input (by itemId x itemRev)
            result.mps_plan_synced, result.item_routing_synced = _enrich_mps_and_item_routing(client)

        logger.info("G-System sync + push confirmation complete")
        result.calendar_synced = len(data.get("calendar", []))
        result.stock_synced    = len(data.get("stock", []))

        # ── Phase 02-04: ABox → Validate → Neo4j ────────────────────────────
        # Disabled — the scheduler/solver that consumed the Neo4j graph was
        # removed, so nothing reads it anymore. Kept commented for reference.
        # _run_neo4j_pipeline(result)

        result.success = True

    except Exception as exc:
        logger.error("G-System sync failed: %s", exc, exc_info=True)
        result.success = False
        result.error = str(exc)

    result.finished_at = datetime.now(timezone.utc)
    return result


def _enrich_prod_plans_with_customer(
    prod_plan_records: list[dict],
    settings: "Any",
) -> None:
    """Enrich prod_plan records with customerNo by following from_id → pd_demand.cust_id.

    G-System API returns prod_plan records without customer info because pd_if_aps_prod_plan
    has no cust_id column. This enrichment queries G-System DB directly via the
    from_id → pd_demand foreign key to resolve the customer for each plan.

    Mutates prod_plan_records in-place — adds 'customerNo' key to each record.
    """
    if not prod_plan_records:
        return

    db_url: str = getattr(settings, "GSYSTEM_DB_URL", "") or ""
    db_user: str = getattr(settings, "GSYSTEM_DB_USER", "") or ""
    db_pass: str = getattr(settings, "GSYSTEM_DB_PASSWORD", "") or ""
    if not db_url or not db_user:
        logger.warning("_enrich_prod_plans_with_customer: GSYSTEM_DB_URL/USER not configured — skipping")
        return

    import re
    # Parse host/port/dbname from URL: postgresql://host:port/dbname
    m = re.match(r"postgresql://([^:]+):(\d+)/(\S+)", db_url)
    if not m:
        logger.warning("_enrich_prod_plans_with_customer: cannot parse GSYSTEM_DB_URL %r", db_url)
        return
    host, port, dbname = m.group(1), int(m.group(2)), m.group(3)

    try:
        import psycopg2
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=db_user, password=db_pass)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.plan_no, d.cust_id
                  FROM demo.pd_if_aps_prod_plan p
                  JOIN demo.pd_demand           d ON p.from_id = d.id
                 WHERE d.cust_id IS NOT NULL
                """
            )
            plan_to_cust: dict[str, str] = {row[0]: str(row[1]) for row in cur.fetchall()}
        conn.close()
    except Exception as exc:
        logger.warning("_enrich_prod_plans_with_customer: DB query failed — %s", exc)
        return

    if not plan_to_cust:
        logger.warning("_enrich_prod_plans_with_customer: JOIN returned 0 rows — customer link skipped")
        return

    enriched = 0
    for rec in prod_plan_records:
        plan_no = rec.get("planNo")
        if plan_no and plan_no in plan_to_cust:
            rec["customerNo"] = plan_to_cust[plan_no]
            enriched += 1
    logger.info("_enrich_prod_plans_with_customer: %d/%d records enriched", enriched, len(prod_plan_records))


def _enrich_equipment(client: "GSystemClient") -> int:
    """Sync equipment for every workcenter via GET /cm/workPlaceEquipmentMng.

    Iterates over workcenters that have a G-System workshopId, fetches their
    equipment list, and upserts aps_equipment rows (keyed by G-System record id).
    Returns total rows synced.
    """
    from app.db.database import SessionLocal
    from app.models.input.workcenter import WorkCenter
    from app.services.gsystem.db_syncer import sync_equipment_by_workshop

    total = 0
    with SessionLocal() as session:
        workcenters = session.execute(
            select(WorkCenter).where(WorkCenter.gsystem_id.isnot(None))
        ).scalars().all()
        for wc in workcenters:
            try:
                records = client.fetch_equipment_by_workshop(int(wc.gsystem_id))
            except Exception as exc:
                logger.warning("fetch_equipment_by_workshop failed for workshopId=%s: %s", wc.gsystem_id, exc)
                continue
            total += sync_equipment_by_workshop(session, wc, records)
        session.commit()
    logger.info("_enrich_equipment: %d equipment rows synced across %d workcenters", total, len(workcenters))
    return total


def _enrich_mps_and_item_routing(client: "GSystemClient") -> tuple[int, int]:
    """Sync MPS plan + per-item routing input.

    Flow:
      1. fetch_mps_plan(settings.GSYSTEM_DEFAULT_PAREA_ID) → upsert aps_mps_plan
      2. Derive unique itemIds from the MPS records
      3. For each item: fetch_item_routing(itemId) → upsert aps_item_routing_spec

    Returns (mps_plan_synced, item_routing_synced).
    """
    from app.config import settings
    from app.db.database import SessionLocal
    from app.models.input.item import Item
    from app.services.gsystem.db_syncer import sync_item_routing, sync_mps_plan

    mps_total = 0
    routing_total = 0
    with SessionLocal() as session:
        try:
            mps_records = client.fetch_mps_plan(settings.GSYSTEM_DEFAULT_PAREA_ID)
        except Exception as exc:
            logger.warning("fetch_mps_plan failed for pareaId=%s: %s", settings.GSYSTEM_DEFAULT_PAREA_ID, exc)
            return 0, 0

        mps_total = sync_mps_plan(session, mps_records)
        session.commit()

        gsys_item_ids = {
            int(r["itemId"]) for r in mps_records if r.get("itemId") is not None
        }
        items = session.execute(
            select(Item).where(Item.gsystem_id.in_(gsys_item_ids))
        ).scalars().all() if gsys_item_ids else []
        item_by_gsys: dict[int, Item] = {i.gsystem_id: i for i in items if i.gsystem_id}

        for gsys_item_id in gsys_item_ids:
            item = item_by_gsys.get(gsys_item_id)
            if item is None:
                logger.debug("_enrich_mps_and_item_routing: item gsystem_id=%s not in APS DB", gsys_item_id)
                continue
            try:
                records = client.fetch_item_routing(gsys_item_id)
            except Exception as exc:
                logger.warning("fetch_item_routing failed itemId=%s: %s", gsys_item_id, exc)
                continue
            routing_total += sync_item_routing(session, item, records)
        session.commit()

    logger.info(
        "_enrich_mps_and_item_routing: mps_plan=%d item_routing=%d across %d items",
        mps_total, routing_total, len(gsys_item_ids) if mps_records else 0,
    )
    return mps_total, routing_total


def _enrich_item_processes(client: "GSystemClient", routing_gsys_ids: set[int]) -> int:
    """Enrich aps_item_process_step with work_time_hours for each routing in the set.

    Flow per routing:
      1. fetch_routing_item_list(routing_id) → list of {routingId, itemId}
      2. For each item: fetch_item_process_list_by_routing(routing_id, item_id)
      3. Upsert aps_item_process_step rows with routing_id + work_time_hours

    Returns total rows enriched.
    """
    from app.db.database import SessionLocal
    from app.models.input.item import Item
    from app.models.input.routing import Routing
    from app.services.gsystem.db_syncer import sync_item_processes_by_routing

    total = 0
    with SessionLocal() as session:
        for gsys_id in routing_gsys_ids:
            routing = session.execute(select(Routing).where(Routing.gsystem_id == gsys_id)).scalar_one_or_none()
            if routing is None:
                logger.warning("_enrich_item_processes: routing gsystem_id=%s not found in DB", gsys_id)
                continue

            try:
                item_records = client.fetch_routing_item_list(gsys_id)
            except Exception as exc:
                logger.warning("fetch_routing_item_list failed for routing %s: %s", gsys_id, exc)
                continue

            # Build item_index: G-System itemId → APS Item (keyed by gsystem_id column)
            gsys_item_ids = [int(r["itemId"]) for r in item_records if r.get("itemId") is not None]
            if not gsys_item_ids:
                continue

            items = session.execute(select(Item).where(Item.gsystem_id.in_(gsys_item_ids))).scalars().all()
            item_index: dict[int, Item] = {item.gsystem_id: item for item in items if item.gsystem_id}

            # TODO: O(N×M) HTTP calls — consider batch API or ThreadPoolExecutor(max_workers=4)
            for rec in item_records:
                gsys_item_id = rec.get("itemId")
                if gsys_item_id is None:
                    continue
                item = item_index.get(int(gsys_item_id))
                if item is None:
                    logger.debug("_enrich_item_processes: item gsystem_id=%s not in APS DB", gsys_item_id)
                    continue
                try:
                    ip_records = client.fetch_item_process_list_by_routing(gsys_id, int(gsys_item_id))
                except Exception as exc:
                    logger.warning(
                        "fetch_item_process_list_by_routing failed routing=%s item=%s: %s",
                        gsys_id, gsys_item_id, exc,
                    )
                    continue

                enriched = sync_item_processes_by_routing(
                    session, routing, ip_records, {int(gsys_item_id): item}
                )
                total += enriched

        session.commit()
    logger.info("_enrich_item_processes: %d rows enriched across %d routings", total, len(routing_gsys_ids))
    return total


# _NEO4J_MAX_RETRIES = 3
# _NEO4J_BACKOFF_BASE = 1  # seconds; wait = base * 2^(attempt-1) → 1s, 2s, 4s
#
#
# def _run_neo4j_pipeline(result: SyncResult) -> None:
#     """Phase 02-04: Build RDF ABox → Validate → Import to Neo4j.
#
#     Modifies *result* in-place with neo4j stats.
#     On failure, sets result.error but does NOT raise — sync Phase 01 already succeeded.
#
#     Disabled — nothing reads the Neo4j graph anymore since the scheduler/solver
#     was removed. Kept here commented out in case it needs to come back.
#     """
#     import time
#     from app.config import settings
#     from app.db.database import SessionLocal
#     from app.services.ontology.abox_builder import build_abox
#     from app.services.ontology.tbox import get_ontology_graph
#
#     # Skip if Neo4j not configured
#     if not settings.APS_NEO4J_URI:
#         logger.info("Neo4j URI not configured — skipping Phase 02-04")
#         result.neo4j_skipped = True
#         return
#
#     # ── Phase 02: Build RDF ABox ─────────────────────────────────────────
#     logger.info("── Phase 02: Building RDF ABox ──────────────────────────────")
#     try:
#         g = get_ontology_graph()
#         with SessionLocal() as session:
#             build_abox(session, g)
#         result.rdf_triples = len(g)
#         logger.info("   Graph: %d triples (TBox + ABox)", len(g))
#     except Exception as exc:
#         logger.error("[Phase 02] ABox build failed: %s", exc, exc_info=True)
#         result.error = f"ABox build failed: {exc}"
#         return
#
#     # ── Phase 03: Validate (non-blocking — log warnings only) ────────────
#     logger.info("── Phase 03: Validating RDF graph ───────────────────────────")
#     try:
#         from app.services.ontology.rdf_validator import validate
#         vr = validate(g)
#         if vr.valid:
#             logger.info("   Validation passed")
#         else:
#             logger.warning("[Phase 03] Validation found %d violation(s):", len(vr.violations))
#             for v in vr.violations:
#                 logger.warning("   • %s", v)
#             # Continue to Neo4j import despite validation warnings
#     except Exception as exc:
#         logger.warning("[Phase 03] Validation error (non-blocking): %s", exc)
#
#     # ── Phase 04: Import to Neo4j ────────────────────────────────────────
#     logger.info("── Phase 04: Importing to Neo4j ─────────────────────────────")
#     from app.services.neo4j.graph_importer import Neo4jConfig, Neo4jImporter
#
#     neo_cfg = Neo4jConfig(
#         uri=settings.APS_NEO4J_URI,
#         user=settings.APS_NEO4J_USER,
#         password=settings.APS_NEO4J_PASSWORD,
#         database=settings.APS_NEO4J_DATABASE,
#     )
#
#     last_exc: Exception | None = None
#     for attempt in range(1, _NEO4J_MAX_RETRIES + 1):
#         try:
#             logger.info("   Connecting to %s (db: %s) [attempt %d/%d]",
#                         neo_cfg.uri, neo_cfg.database, attempt, _NEO4J_MAX_RETRIES)
#             with Neo4jImporter(neo_cfg) as importer:
#                 stats = importer.import_graph(g)
#             result.neo4j_nodes = stats["nodes"]
#             result.neo4j_relationships = stats["relationships"]
#             logger.info("   Imported — nodes=%d relationships=%d",
#                         stats["nodes"], stats["relationships"])
#             return  # success
#         except Exception as exc:
#             last_exc = exc
#             if attempt < _NEO4J_MAX_RETRIES:
#                 wait = _NEO4J_BACKOFF_BASE * (2 ** (attempt - 1))
#                 logger.warning("[Phase 04] Attempt %d/%d failed: %s. Retrying in %ds...",
#                                attempt, _NEO4J_MAX_RETRIES, exc, wait)
#                 time.sleep(wait)
#
#     # All retries failed — record error but don't fail the whole sync
#     logger.error("[Phase 04] Neo4j import failed after %d attempts: %s",
#                  _NEO4J_MAX_RETRIES, last_exc)
#     result.error = f"Neo4j import failed: {last_exc}"

