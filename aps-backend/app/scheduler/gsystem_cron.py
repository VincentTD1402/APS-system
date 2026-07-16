"""Optional weekly/daily G-System sync driven by APScheduler."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_logger
from app.config.config import settings

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_gsystem_cron_scheduler() -> BackgroundScheduler | None:
    """Start background cron if `GSYSTEM_SYNC_CRON_ENABLED` is true."""
    global _scheduler

    if not settings.GSYSTEM_SYNC_CRON_ENABLED:
        logger.info("G-System cron sync disabled (GSYSTEM_SYNC_CRON_ENABLED=false)")
        return None

    try:
        tz = ZoneInfo(settings.GSYSTEM_SYNC_CRON_TIMEZONE)
    except ZoneInfoNotFoundError as e:
        logger.error(
            "Invalid GSYSTEM_SYNC_CRON_TIMEZONE=%r: %s",
            settings.GSYSTEM_SYNC_CRON_TIMEZONE,
            e,
        )
        return None

    expr = settings.GSYSTEM_SYNC_CRON.strip()
    try:
        trigger = CronTrigger.from_crontab(expr, timezone=tz)
    except Exception as e:
        logger.error("Invalid GSYSTEM_SYNC_CRON=%r: %s", expr, e)
        return None

    from app.api.v1.routes.gsystem_sync import run_scheduled_sync

    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(
        run_scheduled_sync,
        trigger=trigger,
        id="gsystem_sync_cron",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    sched.start()
    _scheduler = sched
    logger.info(
        "G-System cron sync enabled expr=%r timezone=%s",
        expr,
        settings.GSYSTEM_SYNC_CRON_TIMEZONE,
    )
    return sched


def shutdown_gsystem_cron_scheduler() -> None:
    """Stop scheduler on app shutdown."""
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
