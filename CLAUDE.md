# CLAUDE.md — LoanFlow

Loan-underwriting maker–checker workbench. Learning project: React + FastAPI +
PostgreSQL, deployed via Docker + GitHub Actions. Also a showcase of a
guard-railed Claude Code workflow (`.claude/`).

## Current phase

See `docs/STATUS.md`. Work the checklist in `docs/ROADMAP.md` top to bottom;
one phase per PR, tests green before moving on.

## Stack & versions

- **api/** — FastAPI, SQLAlchemy 2.0 (imperative-style `Mapped[...]`), Alembic,
  Pydantic v2, psycopg 3. Python 3.12. Deps in `api/requirements.txt`
  (+ `requirements-dev.txt`); tool config in `api/pyproject.toml`.
- **worker/** — APScheduler process. Own deps in `worker/requirements.txt`.
- **web/** — React 18 + TypeScript + Vite. TanStack Query for server state,
  react-hook-form + zod for forms, Axios for HTTP. (Libraries added in P5.)
- **db** — PostgreSQL 16.

## How to run

```bash
cp .env.example .env
docker compose up --build          # web :5173  api :8000  db :5432
```

Common tasks (also in the Makefile; run raw if `make` is unavailable):

| Task            | Command                                                         |
|-----------------|----------------------------------------------------------------|
| Backend tests   | `docker compose run --rm api pytest -q`                         |
| Frontend tests  | `docker compose run --rm web sh -c "npm install && npm test -- --run"` |
| Format (py)     | `docker compose run --rm api ruff format .`                     |
| Lint (py)       | `docker compose run --rm api ruff check .`                      |
| Type-check (py) | `docker compose run --rm api mypy app`                          |
| New migration   | `docker compose run --rm api alembic revision --autogenerate -m "msg"` |
| Apply migrations| `docker compose run --rm api alembic upgrade head`              |

## Repo map

```
api/app/main.py          FastAPI app factory + router registration
api/app/config.py        Settings (pydantic-settings, env-driven)
api/app/db.py            Engine, SessionLocal, get_db dependency
api/app/deps.py          Auth / RBAC dependencies (require_roles) — P1
api/app/security.py      Password hashing + JWT — P1
api/app/models/          SQLAlchemy models — P1+
api/app/routers/         One module per resource; register in main.py
api/app/schemas/         Pydantic request/response models
api/app/services/        Business logic, incl. transition() — P3
api/alembic/             Migration env + versions/
api/tests/               pytest; conftest.py has client/db/auth fixtures
worker/worker/jobs.py    Scheduled jobs (purge_expired_files) — P4
web/src/                 React app
docs/                    ROADMAP, ARCHITECTURE, STATE_MACHINE, adr/, ai-workflow
```

## Conventions

- **Never write a status column directly.** All state changes for loan files and
  review tasks go through `transition()` in `api/app/services/state_machine.py`
  (added P3). A hook flags raw `\.status\s*=` writes in routers.
- One router module per resource; register it in `api/app/main.py`.
- Request/response bodies are Pydantic models in `api/app/schemas/` — no raw dicts.
- RBAC is enforced with the `require_roles(...)` dependency on the route, not in
  handler bodies or middleware.
- DB session: one per request via the `get_db` dependency (`yield`, commit on
  success, rollback on exception). Never open a second session in a handler.
- Money is `Numeric(14, 2)`, never float.
- Every feature ships with a test. PRs with new endpoints need endpoint tests
  covering the allowed role and at least one forbidden role.
- Frontend: all server state through TanStack Query hooks in
  `web/src/features/<area>/`. Every screen handles loading, empty, and error.

## State machine (summary — full detail in docs/STATE_MACHINE.md)

- **Loan file:** `DRAFT → SUBMITTED → IN_REVIEW → FUND_READY_TO_RELEASE → PURGED`
- **Review task:** `PENDING_MAKER → PENDING_CHECKER → COMPLETED`, with
  `PENDING_CHECKER → CHANGES_REQUESTED → PENDING_MAKER` on rejection.
- A file reaches `FUND_READY_TO_RELEASE` only when all 4 review tasks are
  `COMPLETED`. Housekeeping purges it `PURGE_AFTER_DAYS` (default 30) later.

## RBAC matrix

| Role         | Team | Can                                                        |
|--------------|------|-----------------------------------------------------------|
| OPS_MAKER    | OPS  | create/submit loan files, upload documents                 |
| OPS_CHECKER  | OPS  | review the intake step                                     |
| UW_MAKER     | UW   | perform a review task (maker side)                         |
| UW_CHECKER   | UW   | approve/reject a review task (checker side)                |
| ADMIN        | —    | reassign tasks, trigger housekeeping, read everything      |

A checker can never be the maker of the same task (`checker_id != maker_id`).

## Claude Code workflow

- **Subagents** live in `.claude/agents/`. Use `workflow-modeler` for any
  transition change, `security-reviewer` before merging auth/route changes,
  `db-migrator` when models change, `test-writer` after each feature.
- **Skills** in `.claude/skills/`: `add-endpoint`, `add-migration`,
  `add-scheduled-job`, `add-page`, `seed-demo-data`, `deploy`.
- **Hooks** in `.claude/settings.json` auto-format/lint on write, run tests on
  Stop, and block dangerous Bash. Edit them via the `update-config` skill.
- **Agentic loop:** `/loop implement the next unchecked item in docs/ROADMAP.md —
  tests first, make them pass, run the suite, tick the item, commit`.

## Do not touch

- `.env` or any real secret. Secrets reach containers as env vars only.
- Production database directly. No `fly deploy` off `main` (a hook blocks both).
