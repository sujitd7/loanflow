---
name: add-scheduled-job
description: Add a recurring background job to the LoanFlow worker (APScheduler). Use for anything that runs on a schedule — purges, SLA flags, digest emails.
---

# Add a scheduled job

The worker lives in `worker/worker/`. `main.py` builds the scheduler; jobs are
functions in `jobs.py`.

1. **Write the job** in `worker/worker/jobs.py`:
   - Signature `def job_name() -> None`. Opens its own `Session` (worker has its
     own `db.py`), commits explicitly, closes in a `finally`.
   - **Idempotent**: safe to run twice with no extra effect. Guard on current
     state; key any inserts on a natural unique column.
   - **Single-runner**: wrap the body in a Postgres advisory lock
     (`pg_try_advisory_lock(<int key>)`) and return early if not acquired, so
     multiple worker replicas don't collide.
   - Log start, counts, and finish as structured JSON. Never raise out of the job
     — catch, log, and let the next run retry.

2. **Register** in `worker/worker/main.py`:
   ```python
   scheduler.add_job(job_name, CronTrigger.from_crontab(settings.SOME_CRON),
                     id="job_name", max_instances=1, coalesce=True)
   ```
   Add the cron string to `worker/worker/config.py` and `.env.example`.

3. **Manual trigger for demos** — if operators need to run it on demand, add an
   `ADMIN`-only endpoint in the API that calls the same job function (import it or
   duplicate the logic in a shared module).

4. **Test** in `worker/tests/` with `freezegun`: advance time, run the job, assert
   the effect; run it again, assert nothing else changed.
