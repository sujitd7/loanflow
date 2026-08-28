# Architecture

## Containers

| Service  | Image base            | Responsibility |
|----------|-----------------------|----------------|
| `web`    | node (dev) / nginx (prod) | Serve the React SPA; in prod, proxy `/api` to `api` |
| `api`    | python:3.12-slim      | FastAPI (uvicorn/gunicorn). Stateless. All reads/writes to Postgres |
| `worker` | python:3.12-slim      | APScheduler. Housekeeping/purge + SLA jobs. Advisory-locked so replicas don't double-run |
| `db`     | postgres:16           | System of record |
| storage  | volume (dev) / object store (prod) | Uploaded loan documents; deleted on purge |

Local dev: `docker compose up` runs all of the above with hot reload on `api`
and `web`. Production runs the same `api` / `web` / `worker` images against a
managed Postgres.

## Request flow

```
Browser ──/──> web (nginx) ──/api──> api (FastAPI) ──SQL──> Postgres
                                       │
                              JWT verify (require_roles)
                                       │
                              router → service → transition()/query
```

## Backend layering

```
routers/    HTTP only: validate input, call a service, serialize a schema
schemas/    Pydantic v2 request/response models
services/   business logic; state_machine.transition() is the only status writer
models/     SQLAlchemy 2.0 ORM
db.py       engine + get_db (one session per request, commit/rollback)
deps.py     auth + RBAC dependencies
```

## Data model (core)

`users` · `loan_files` · `loan_documents` · `review_tasks` · `task_events` ·
`loan_file_archive`. Full column list and rationale: see the blueprint and
`docs/STATE_MACHINE.md`.

Key indexes:
- `review_tasks (maker_id, status)`, `review_tasks (checker_id, status)` — task inbox
- `loan_files (status, fund_ready_at)` — housekeeping scan
- `task_events (loan_file_id, created_at)` — activity feed
- `UNIQUE (loan_file_id, check_type)` on `review_tasks` — idempotent submit

## Background jobs

- `purge_expired_files` — daily (`HOUSEKEEPING_CRON`). Finds
  `FUND_READY_TO_RELEASE` files older than `PURGE_AFTER_DAYS`, archives a
  PII-free summary, deletes documents and the source rows, logs an event.
  Idempotent; wrapped in `pg_try_advisory_lock`.

## Deployment

CI on `main` builds three images, pushes to GHCR, deploys, runs
`alembic upgrade head` as a release step, and smoke-tests `/health`. Migrations
are expand/contract so a code rollback never needs a DB rollback. See the
`deploy` skill for the runbook.

## Decisions

Recorded as ADRs in `docs/adr/`.
