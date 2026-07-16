"""Dump PostgreSQL and Neo4j databases to backups/ directory.

Usage:
    uv run python app/scripts/dump_databases.py             # dump both
    uv run python app/scripts/dump_databases.py --clean     # dump + delete files > 60 days
    uv run python app/scripts/dump_databases.py --clean-only  # only delete old files
"""

import argparse
import gzip
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running as a script from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config import get_logger, settings  # noqa: E402

logger = get_logger(__name__)

BACKUP_DIR = Path(__file__).parent.parent.parent / "backups"
RETENTION_DAYS = 60


# ── PostgreSQL ────────────────────────────────────────────────────────────────

def dump_postgresql() -> Path:
    """Dump PostgreSQL via pg_dump, compress to .sql.gz, return output path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"pg_aps_{ts}.sql.gz"

    logger.info("Dumping PostgreSQL → %s", out.name)
    proc = subprocess.run(
        ["pg_dump", settings.APS_DB_URL],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {proc.stderr.decode().strip()}")

    with gzip.open(out, "wb") as f:
        f.write(proc.stdout)

    size_kb = out.stat().st_size / 1024
    logger.info("PostgreSQL dump done — %s (%.1f KB)", out.name, size_kb)
    return out


# ── Neo4j ─────────────────────────────────────────────────────────────────────

def dump_neo4j() -> Path:
    """Export all Neo4j nodes + relationships as JSON, compress to .json.gz."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"neo4j_aps_{ts}.json.gz"

    logger.info("Exporting Neo4j → %s", out.name)
    from neo4j import GraphDatabase  # noqa: PLC0415 (lazy import, neo4j optional dep)

    driver = GraphDatabase.driver(
        settings.APS_NEO4J_URI,
        auth=(settings.APS_NEO4J_USER, settings.APS_NEO4J_PASSWORD),
    )
    try:
        with driver.session(database=settings.APS_NEO4J_DATABASE) as session:
            nodes = session.run(
                "MATCH (n) RETURN labels(n) AS labels, properties(n) AS props"
            ).data()
            rels = session.run(
                "MATCH (a)-[r]->(b) "
                "RETURN a.id AS from_id, type(r) AS type, b.id AS to_id, "
                "properties(r) AS props"
            ).data()
    finally:
        driver.close()

    data = {"nodes": nodes, "relationships": rels}
    with gzip.open(out, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)

    size_kb = out.stat().st_size / 1024
    logger.info(
        "Neo4j export done — %s (%.1f KB) — %d nodes, %d relationships",
        out.name, size_kb, len(nodes), len(rels),
    )
    return out


# ── Rotation ──────────────────────────────────────────────────────────────────

def clean_old_backups() -> int:
    """Delete files in BACKUP_DIR older than RETENTION_DAYS. Return count deleted."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0
    for f in BACKUP_DIR.iterdir():
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            f.unlink()
            logger.info("Deleted old backup: %s", f.name)
            deleted += 1
    logger.info("Rotation done — removed %d file(s) older than %d days", deleted, RETENTION_DAYS)
    return deleted


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main(*, clean: bool = False, clean_only: bool = False) -> None:
    BACKUP_DIR.mkdir(exist_ok=True)

    if clean_only:
        clean_old_backups()
        return

    dump_postgresql()
    dump_neo4j()

    if clean:
        clean_old_backups()

    logger.info("Backup complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dump PostgreSQL + Neo4j databases to backups/")
    parser.add_argument("--clean", action="store_true", help="Also delete backups older than 60 days")
    parser.add_argument("--clean-only", action="store_true", help="Only delete old backups, skip dump")
    args = parser.parse_args()
    try:
        main(clean=args.clean, clean_only=args.clean_only)
    except Exception as exc:
        logger.critical("Backup failed: %s", exc)
        sys.exit(1)
