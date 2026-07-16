"""APS pipeline orchestration — Phase 01 only (G-System sync → aps_input tables).

Usage:
    uv run python app/scripts/run_pipeline.py                    # sync from G-System
    uv run python app/scripts/run_pipeline.py --use-mock         # skip G-System sync (use existing DB data)
    uv run python app/scripts/run_pipeline.py --use-mock --reset # drop+recreate tables first (after model changes)

Failure strategy:
    Phase 01 fail → raise GSystemSyncError (pipeline stops, DB rollback)

NOTE: Phase 02 (RDF ABox) / Phase 03 (validate) / Phase 04 (Neo4j import) are
disabled — nothing in the app reads the Neo4j graph anymore since the
scheduler/solver was removed. Code kept commented below for reference /
future reactivation; app.services.ontology and app.services.neo4j still exist.
"""

import argparse
import sys
# import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import get_logger
# from app.config import settings
# from app.db.database import SessionLocal
# from app.services.ontology.abox_builder import build_abox
# from app.services.ontology.rdf_validator import validate
# from app.services.ontology.tbox import get_ontology_graph

logger = get_logger(__name__)

# ── Retry config for Phase 04 ─────────────────────────────────────────────────
# _NEO4J_MAX_RETRIES = 3
# _NEO4J_BACKOFF_BASE = 1  # seconds; wait = base * 2^(attempt-1) → 1s, 2s, 4s


# ── Pipeline exceptions ───────────────────────────────────────────────────────

class PipelineError(Exception):
    """Base class for all pipeline failures."""


class GSystemSyncError(PipelineError):
    """Phase 01 failed — G-System API fetch or DB sync error."""


# class ABoxBuildError(PipelineError):
#     """Phase 02 failed — RDF ABox construction error."""
#
#
# class ValidationError(PipelineError):
#     """Phase 03 failed — OWL-RL or SHACL violations detected."""
#
#
# class Neo4jImportError(PipelineError):
#     """Phase 04 failed — Neo4j import failed after all retries."""


# ── Pipeline ──────────────────────────────────────────────────────────────────

def main(use_mock: bool = False, reset: bool = False) -> None:
    # ── Phase 01: Sync from G-System API (or skip with --use-mock) ────────────
    if use_mock:
        logger.info("── Phase 01: Seeding mock data ───────────────────────────")
        from app.scripts.seed_mock_data import seed
        seed(reset=reset)
        logger.info("   Mock data seeded (upsert — safe to re-run)")
    else:
        logger.info("── Phase 01: Syncing from G-System API ───────────────────")
        from app.services.gsystem.sync_service import run_gsystem_sync
        result = run_gsystem_sync()
        if not result.success:
            raise GSystemSyncError(f"G-System sync failed: {result.error}")
        logger.info("   Synced entities: %s", {k: v["synced"] for k, v in result.counts.items()})
        logger.info("   Calendar synced: %d entries", result.calendar_synced)
        logger.info("   Stock synced: %d entries", result.stock_synced)
        logger.info("   Item processes enriched: %d", result.item_processes_enriched)

    # ── Phase 02: Build RDF ABox ───────────────────────────────────────────────
    # logger.info("── Phase 02: Building RDF ABox ───────────────────────────────")
    # try:
    #     g = get_ontology_graph()
    #     with SessionLocal() as session:
    #         build_abox(session, g)
    #     logger.info("   Graph: %d triples (TBox + ABox)", len(g))
    # except Exception as exc:
    #     logger.error("[Phase 02] ABox build failed: %s", exc)
    #     raise ABoxBuildError(f"ABox build failed: {exc}") from exc
    #
    # # ── Phase 03: Validate ────────────────────────────────────────────────────
    # logger.info("── Phase 03: Validating RDF graph ────────────────────────")
    # result = validate(g)
    # if result.valid:
    #     logger.info("   Validation passed ✓")
    # else:
    #     logger.error("[Phase 03] Validation found %d violation(s):", len(result.violations))
    #     for v in result.violations:
    #         logger.error("   • %s", v)
    #     # Clear in-memory graph — prevent any accidental downstream use
    #     g.remove((None, None, None))
    #     raise ValidationError(
    #         f"Validation failed with {len(result.violations)} violation(s). "
    #         "Import rejected. Graph cleared."
    #     )
    #
    # # ── Phase 04: Import to Neo4j ─────────────────────────────────────────────
    # logger.info("── Phase 04: Importing to Neo4j ──────────────────────────")
    # from app.services.neo4j.graph_importer import Neo4jConfig, Neo4jImporter
    #
    # neo_cfg = Neo4jConfig(
    #     uri=settings.APS_NEO4J_URI,
    #     user=settings.APS_NEO4J_USER,
    #     password=settings.APS_NEO4J_PASSWORD,
    #     database=settings.APS_NEO4J_DATABASE,
    # )
    #
    # last_exc: Exception | None = None
    # for attempt in range(1, _NEO4J_MAX_RETRIES + 1):
    #     try:
    #         logger.info(
    #             "   Connecting to %s (db: %s) [attempt %d/%d]",
    #             neo_cfg.uri, neo_cfg.database, attempt, _NEO4J_MAX_RETRIES,
    #         )
    #         with Neo4jImporter(neo_cfg) as importer:
    #             stats = importer.import_graph(g)
    #         logger.info(
    #             "   Imported — nodes=%d relationships=%d",
    #             stats["nodes"], stats["relationships"],
    #         )
    #         last_exc = None
    #         break  # success
    #     except Exception as exc:
    #         last_exc = exc
    #         if attempt < _NEO4J_MAX_RETRIES:
    #             wait = _NEO4J_BACKOFF_BASE * (2 ** (attempt - 1))
    #             logger.warning(
    #                 "[Phase 04] Attempt %d/%d failed: %s. Retrying in %ds...",
    #                 attempt, _NEO4J_MAX_RETRIES, exc, wait,
    #             )
    #             time.sleep(wait)
    #         else:
    #             logger.error("[Phase 04] All %d attempts failed.", _NEO4J_MAX_RETRIES)
    #
    # if last_exc is not None:
    #     raise Neo4jImportError(
    #         f"Neo4j import failed after {_NEO4J_MAX_RETRIES} attempts: {last_exc}"
    #     ) from last_exc

    logger.info("── Pipeline complete ─────────────────────────────────────────")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run APS pipeline: G-System sync")
    parser.add_argument("--use-mock", action="store_true", help="Skip G-System sync, use existing DB data")
    parser.add_argument("--reset", action="store_true", help="Drop + recreate all tables before seeding (only with --use-mock)")
    args = parser.parse_args()
    try:
        main(use_mock=args.use_mock, reset=args.reset)
    except PipelineError as exc:
        logger.critical("Pipeline aborted: %s", exc)
        sys.exit(1)
