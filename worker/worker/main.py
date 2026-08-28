import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import settings
from .jobs import purge_expired_files

logging.basicConfig(level=settings.log_level)
log = logging.getLogger("worker")


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        purge_expired_files,
        CronTrigger.from_crontab(settings.housekeeping_cron),
        id="purge_expired_files",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    return scheduler


def main() -> None:
    scheduler = build_scheduler()
    scheduler.start()
    log.info("worker started; jobs=%s", [job.id for job in scheduler.get_jobs()])
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        log.info("worker stopped")


if __name__ == "__main__":
    main()
