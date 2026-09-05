# LoanFlow

A **maker–checker loan-underwriting workbench**. Operations logs an incoming loan
file; Underwriting runs four independent maker–checker verifications (credit, KYC,
payment eligibility, tax return); once all four pass the file is marked
**fund-ready-to-release**; a housekeeping job purges it 30 days later, leaving only
a PII-free audit summary.

It is built in the open to practise **React + TypeScript** and
**FastAPI + PostgreSQL** end to end — with the patterns a real system-of-record
needs (RBAC, an explicit state machine, optimistic locking, an append-only audit
trail, expand/contract migrations) rather than CRUD — and to run a deliberate,
**guard-railed [Claude Code](ai-workflow.md) workflow** on top of it.

!!! info "Status: early"
    The backend foundation (identity + RBAC) is done and CI-green; the loan-file
    domain and the React UI are next. See [Status](STATUS.md) and the
    [Roadmap](ROADMAP.md).

## Start here

| If you want to…                              | Read |
|----------------------------------------------|------|
| Understand how the pieces fit together        | [Architecture](ARCHITECTURE.md) |
| See the exact status transitions and guards   | [State machine](STATE_MACHINE.md) |
| Follow the build plan, phase by phase         | [Roadmap](ROADMAP.md) · [Status](STATUS.md) |
| Run the stack on your machine                 | [Local dev](LOCAL_DEV.md) |
| See how Claude Code is used with guard-rails  | [AI workflow](ai-workflow.md) |
| Know *why* a given choice was made            | [ADRs](adr/0001-record-architecture-decisions.md) |
| Work on this documentation site               | [Contributing to the docs](CONTRIBUTING-docs.md) |

## The stack

| Layer     | Choice |
|-----------|--------|
| Frontend  | React 18, TypeScript, Vite, TanStack Query, react-hook-form + zod |
| Backend   | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, psycopg 3, Argon2 + JWT |
| Database  | PostgreSQL 16 |
| Jobs      | APScheduler in a dedicated worker process ([ADR 0002](adr/0002-apscheduler-over-celery.md)) |
| Deploy    | Docker images → Fly.io / single VPS (planned) |
| CI/CD     | GitHub Actions → GHCR |

## Run it locally

With Docker:

```bash
cp .env.example .env
docker compose up --build          # web :5173  api :8000  db :5432
```

No working Docker? The stack also runs natively with a Python venv +
`npm run dev` against any Postgres — see [Local dev](LOCAL_DEV.md).

## RBAC matrix

| Role         | Team | Can |
|--------------|------|-----|
| `OPS_MAKER`  | OPS  | create / submit loan files, upload documents |
| `OPS_CHECKER`| OPS  | review the intake step |
| `UW_MAKER`   | UW   | perform a review task (maker side) |
| `UW_CHECKER` | UW   | approve / reject a review task (checker side) |
| `ADMIN`      | —    | reassign tasks, trigger housekeeping, read everything |

A checker can never be the maker of the same task (`checker_id != maker_id`).
