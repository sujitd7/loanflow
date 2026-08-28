# Roadmap

One phase per PR. Tests green before the next. The agentic loop works this list:
`/loop implement the next unchecked item — tests first, make them pass, run the
suite, tick the item, commit`.

## P0 — Foundation & tooling
- [x] Monorepo layout, `docker-compose.yml`, `.env.example`
- [x] FastAPI `/health` (DB check) + Vite React app that calls it
- [x] Worker skeleton (APScheduler, no jobs)
- [x] pre-commit, `CLAUDE.md`, `.claude/` hooks + agents + skills
- [x] CI skeleton (lint + test on PR)
- [x] `git init`, first commit
- [ ] Create the GitHub repo, push, branch protection on `main`
- [ ] Confirm `docker compose up` is green on the dev machine

## P1 — Identity, roles, RBAC
- [ ] `users` model + Alembic migration; Argon2 hashing in `app/security.py`
- [ ] `POST /auth/login`, `POST /auth/refresh` (rotating), `GET /auth/me`
- [ ] `Role` enum + `require_roles(...)` dependency in `app/deps.py`
- [ ] `conftest.py` fixtures: `client`, `db`, per-role auth headers
- [ ] Tests: login ok/bad, expired token, each role vs a protected probe route

## P2 — Loan-file intake + task generation
- [ ] `loan_files`, `loan_documents` models + migration
- [ ] `POST /loan-files` (OPS_MAKER), document upload, size/type limits
- [ ] `POST /loan-files/{id}/submit` — atomically create 4 assigned review tasks
      (round-robin within UW), write `task_events`, idempotent
- [ ] `GET /loan-files` — pagination + filtering + per-file task counts (no N+1)
- [ ] `GET /loan-files/{id}` — file + tasks + activity feed
- [ ] Tests incl. idempotent submit and the N+1 guard

## P3 — Maker–checker flow + state machine + audit
- [ ] `review_tasks` model with `version`; `task_events` model
- [ ] `app/services/state_machine.py` — `transition()` guard, single source of truth
- [ ] `POST /tasks/{id}/maker-submit` (findings → PENDING_CHECKER, needs `version`)
- [ ] `POST /tasks/{id}/checker-decide` (approve → COMPLETED / reject → CHANGES_REQUESTED)
- [ ] Enforce `checker_id != maker_id`; last task completing → file FUND_READY_TO_RELEASE
- [ ] `GET /tasks?assignee=me&as=maker|checker&status=`
- [ ] Tests: every transition, stale-version conflict, self-check rejection

## P4 — Completion & housekeeping
- [ ] Worker job `purge_expired_files()` — advisory-locked, idempotent
- [ ] Archive summary row (no PII) + delete documents + `task_events` entry
- [ ] `POST /admin/run-housekeeping` (ADMIN) for demos; `PURGE_AFTER_DAYS` config
- [ ] Tests with `freezegun`; run job twice → one archive row

## P5 — Frontend foundation + core flows
- [ ] Router, auth context, `RequireAuth` / `RequireRole`
- [ ] `lib/http.ts` Axios instance + refresh interceptor + request queue
- [ ] TanStack Query setup; react-hook-form + zod
- [ ] Screens: Login (with demo-login buttons), Submission wizard, My Tasks,
      Loan File detail (4-check panel), Review drawer
- [ ] Optimistic task actions + rollback; toasts; error boundary
- [ ] RTL + MSW tests for each screen

## P6 — Dashboards
- [ ] `GET /dashboard/team` and `GET /dashboard/loan-files` aggregation endpoints
- [ ] SQL: group by, `date_trunc`, filtered aggregates, turnaround
- [ ] Recharts: status funnel, per-member table + sparklines, aging histogram
- [ ] Filters by team + date range; tune with `EXPLAIN ANALYZE`

## P7 — Hardening, E2E, seed data
- [ ] Playwright: full happy path + a reject loop
- [ ] Auth rate limiting; JSON logging + request IDs
- [ ] `app/seed_demo.py` — deterministic demo board (see seed-demo-data skill)
- [ ] Error tracking (Sentry/OTel); index audit; `SECURITY.md`
- [ ] `/security-review` pass

## P8 — Deploy + CI/CD
- [ ] Multi-stage Dockerfiles (api, web, worker) — prod stages
- [ ] `infra/` deploy config (`fly.toml` per service, or VPS compose + Caddy)
- [ ] `.github/workflows/deploy.yml` — build, push GHCR, deploy, migrate, smoke
- [ ] Secrets wired; rolling deploy; rollback tested and documented
- [ ] README badges; live URL

## P9 — Showcase
- [ ] README hero GIF, live link, demo creds, architecture diagram
- [ ] `docs/ARCHITECTURE.md` finalised; 3–5 ADRs
- [ ] `docs/ai-workflow.md` with real hook/subagent/skill/loop examples
- [ ] `DEMO.md` 3-minute script; 2-minute Loom; pin the repo
