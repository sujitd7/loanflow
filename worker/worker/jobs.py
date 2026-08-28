import logging

from sqlalchemy import text

from .config import settings
from .db import SessionLocal

log = logging.getLogger("worker.jobs")

# Arbitrary constant key for pg_advisory_lock so only one replica runs the purge.
PURGE_LOCK_KEY = 91_001


def purge_expired_files() -> None:
    """Purge loan files that have been FUND_READY_TO_RELEASE longer than the
    retention window.

    Idempotent and single-runner: wrapped in a Postgres advisory lock, and the
    real implementation (P4) keys its archive inserts on the original file id so a
    second run is a no-op.

    P0: wiring only — acquire the lock, log, release.
    """
    session = SessionLocal()
    try:
        got_lock = session.execute(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": PURGE_LOCK_KEY}
        ).scalar()
        if not got_lock:
            log.info("purge_expired_files: lock held by another worker, skipping")
            return
        try:
            log.info(
                "purge_expired_files: wired, retention=%s days (no-op until P4)",
                settings.purge_after_days,
            )
            # P4:
            #   cutoff = now(UTC) - timedelta(days=settings.purge_after_days)
            #   for file in fund_ready files with fund_ready_at < cutoff:
            #       insert loan_file_archive summary (no PII)
            #       delete loan_documents + source rows
            #       insert task_events(action="PURGED")
            #   session.commit()
        finally:
            session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": PURGE_LOCK_KEY})
            session.commit()
    except Exception:
        session.rollback()
        log.exception("purge_expired_files failed")
    finally:
        session.close()
