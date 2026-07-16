"""Sync routes — trigger G-System → APS DB sync via HTTP.

POST /sync/run   — kick off a sync, runs in background, returns job_id
GET  /sync/jobs/{job_id} — poll result of a running/completed sync
"""

from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_logger
from app.db.database import get_db, SessionLocal
from app.models.output.gsystem_sync_job import GsystemSyncJob
from app.schemas.sync import SyncRunResponse, EntityCount
from app.services.gsystem.sync_service import SyncResult

logger = get_logger(__name__)

router = APIRouter()

# Guard: only one sync at a time — Event is thread-safe without manual lock
_sync_idle = threading.Event()
_sync_idle.set()  # starts idle (not running)


def _try_acquire_sync() -> bool:
    """Atomically check-and-set sync running state. Returns True if acquired."""
    if not _sync_idle.is_set():
        return False
    _sync_idle.clear()
    return True


def _release_sync() -> None:
    """Mark sync as idle — safe to call from any thread."""
    _sync_idle.set()


def _save_result(job_id: str, result: SyncResult) -> None:
    """Persist SyncResult to DB in a dedicated session."""
    db = SessionLocal()
    try:
        job = db.get(GsystemSyncJob, job_id)
        if job is None:
            return
        job.status = "completed" if result.success else "failed"
        job.finished_at = result.finished_at
        job.success = result.success
        job.error = result.error
        job.counts = result.counts
        job.calendar_synced = result.calendar_synced
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist sync job %s", job_id)
    finally:
        db.close()


def _run_sync(job_id: str) -> None:
    """Blocking sync called in a background thread via BackgroundTasks."""
    from app.services.gsystem.sync_service import run_gsystem_sync
    try:
        result = run_gsystem_sync()
        _save_result(job_id, result)
    finally:
        _release_sync()


def run_scheduled_sync() -> None:
    """Run G-System sync from APScheduler; shares `_sync_idle` with POST /run."""
    from app.services.gsystem.sync_service import run_gsystem_sync

    if not _try_acquire_sync():
        logger.warning("Scheduled G-System sync skipped: a sync is already running")
        return
    try:
        result = run_gsystem_sync()
        logger.info(
            "Scheduled G-System sync finished success=%s calendar_synced=%s",
            result.success,
            result.calendar_synced,
        )
        if result.error:
            logger.warning("Scheduled G-System sync reported error=%s", result.error)
    except Exception:
        logger.exception("Scheduled G-System sync failed")
    finally:
        _release_sync()


def _to_response(job: GsystemSyncJob) -> SyncRunResponse:
    return SyncRunResponse(
        started_at=job.started_at,
        finished_at=job.finished_at,
        success=job.success or False,
        error=job.error,
        counts={k: EntityCount(**v) for k, v in (job.counts or {}).items()},
        calendar_synced=job.calendar_synced,
        neo4j_nodes=job.neo4j_nodes,
        neo4j_relationships=job.neo4j_relationships,
        rdf_triples=job.rdf_triples,
    )


@router.post("/run", status_code=202)
def trigger_sync(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Kick off G-System → APS DB sync in the background.

    Returns immediately with a job_id to poll.
    Returns 409 if a sync is already in progress.
    """
    if not _try_acquire_sync():
        raise HTTPException(status_code=409, detail="A sync is already running")

    job_id = str(uuid.uuid4())
    job = GsystemSyncJob(job_id=job_id, status="running")
    db.add(job)
    db.commit()

    background_tasks.add_task(_run_sync, job_id)
    return {"job_id": job_id, "status": "accepted"}


@router.get("/jobs/{job_id}", response_model=SyncRunResponse)
def get_sync_job(job_id: str, db: Session = Depends(get_db)) -> SyncRunResponse:
    """Poll a sync job by ID.

    Returns 202 while running, 200 when done (check `success` field).
    """
    job = db.get(GsystemSyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "running":
        raise HTTPException(
            status_code=202,
            detail={"job_id": job_id, "status": "running"},
        )

    return _to_response(job)
