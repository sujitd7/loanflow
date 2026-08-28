# 2. APScheduler in a worker process, not Celery + Redis

Date: 2026-08-28

## Status

Accepted

## Context

LoanFlow needs recurring background work: a daily housekeeping job that purges
loan files 30 days after they become fund-ready, plus a nightly SLA/overdue flag.
There is no user-triggered async work, no fan-out, no need for task result
tracking or retries-with-backoff queues.

Options considered:
1. **Celery + Redis** — the "standard" Python task queue. Adds a broker container,
   a result backend, worker + beat processes, and serialization concerns.
2. **APScheduler in a dedicated worker container** — a scheduler library running
   cron-style jobs in one long-lived process.
3. **`pg_cron`** — schedule inside Postgres. Ties scheduling to the DB, harder to
   test and to reason about in application terms.

## Decision

Use **APScheduler** in a dedicated `worker` service. Guarantee single execution
across replicas with a Postgres advisory lock inside each job, and make every job
idempotent regardless.

## Consequences

- One fewer piece of infrastructure (no Redis) — simpler local dev and deploy.
- Jobs are plain Python functions, trivially unit-testable with `freezegun`.
- No built-in distributed queue: if the project later needs user-triggered async
  work or heavy fan-out, revisit with Celery or a Postgres-backed queue
  (e.g. `pgqueuer`). This ADR would be superseded.
- Multi-replica safety is our responsibility — handled by the advisory lock +
  idempotency, and asserted in tests.
