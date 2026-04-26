"""APScheduler wrapper — weekly Sunday 03:00 (spec 7.4)."""
import logging
from typing import Optional

log = logging.getLogger(__name__)
_scheduler = None


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.pipeline.evolution.collector import refresh_all_metrics

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        refresh_all_metrics,
        trigger="cron",
        day_of_week="sun",
        hour=3,
        id="phase2_refresh",
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    log.info("Phase 2 scheduler started (cron: Sun 03:00 UTC)")


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_run() -> Optional[str]:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("phase2_refresh")
    return job.next_run_time.isoformat() if job and job.next_run_time else None
