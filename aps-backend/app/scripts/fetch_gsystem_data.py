"""Fetch all G-System APS endpoints and save raw JSON to docs/gsystem/.

Usage:
    uv run python3 app/scripts/fetch_gsystem_data.py

    # Override output dir
    uv run python3 app/scripts/fetch_gsystem_data.py --out data/raw

Reads env from .env via app.config.settings.
Output files: docs/gsystem/<entity>.json  (one file per endpoint)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import settings, get_logger
from app.services.gsystem.api_client import (
    GSystemClient,
    GSystemConfig,
    build_item_id_to_no,
)

logger = get_logger(__name__)

# ── Entities to fetch (skip: cust, equip — not in ontology) ──────────────────

_FETCH_MAP = {
    "items":       "fetch_items",
    "bom":         "fetch_bom",
    "workcenters": "fetch_workcenters",
    "routings":    "fetch_routings",
    "operations":  "fetch_operations",
    "demands":     "fetch_demands",
}


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = GSystemConfig(
        base_url=settings.GSYSTEM_BASE_URL.rstrip("/"),
        api_key=settings.GSYSTEM_API_KEY,
        timeout=settings.GSYSTEM_TIMEOUT,
        retries=settings.GSYSTEM_RETRIES,
        all_data=settings.GSYSTEM_ALL_DATA,
    )
    logger.info("Connecting to %s", cfg.base_url)

    results: dict[str, list] = {}
    failed: list[str] = []

    with GSystemClient(cfg) as client:
        for name, method in _FETCH_MAP.items():
            logger.info("Fetching %s ...", name)
            try:
                records = getattr(client, method)()
                results[name] = records
                logger.info("  → %d records", len(records))
            except Exception as exc:
                logger.error("  FAILED: %s", exc)
                failed.append(name)

    # ── Save each entity to its own JSON file ─────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for name, records in results.items():
        out_file = out_dir / f"{name}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(
                {"fetched_at": timestamp, "count": len(records), "result": records},
                f,
                ensure_ascii=False,
                indent=2,
                default=str,  # handle dates/decimals
            )
        logger.info("Saved %s → %s (%d records)", name, out_file, len(records))

    # ── Build and save lookup index ───────────────────────────────────────────
    if "items" in results:
        id_to_no = build_item_id_to_no(results["items"])
        index_file = out_dir / "item_id_to_no.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(id_to_no, f, ensure_ascii=False, indent=2)
        logger.info("Saved item_id_to_no index → %s (%d entries)", index_file, len(id_to_no))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n── Fetch summary ──────────────────────────────")
    for name, records in results.items():
        print(f"  {name:12}: {len(records):>4} records  →  {out_dir / f'{name}.json'}")
    if failed:
        print(f"\n  FAILED: {', '.join(failed)}")
        sys.exit(1)
    print(f"\n  Output dir: {out_dir.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch G-System data and save to JSON files.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parents[2] / "docs" / "gsystem",
        help="Output directory (default: docs/gsystem/)",
    )
    args = parser.parse_args()
    main(args.out)
