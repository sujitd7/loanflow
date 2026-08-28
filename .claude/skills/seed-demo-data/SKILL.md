---
name: seed-demo-data
description: Regenerate LoanFlow's deterministic demo dataset — users for every role and loan files in every state — for local dev and the live showcase. Use when the demo board needs refreshing or extending.
---

# Seed demo data

The seeder is `api/app/seed_demo.py`, run with
`docker compose run --rm api python -m app.seed_demo` (or `make seed`).

It must be **deterministic and idempotent**: fixed seed, upsert by email /
natural key, safe to run repeatedly. Wipe-and-rebuild is fine for local but the
production showcase seed must not delete real activity — gate destructive mode
behind `--reset`.

Produce:

- **Users** — one per role, password `demo1234`:
  `ops.maker@demo.loanflow`, `ops.checker@demo.loanflow`,
  `uw.maker@demo.loanflow`, `uw.maker2@demo.loanflow`,
  `uw.checker@demo.loanflow`, `uw.checker2@demo.loanflow`, `admin@demo.loanflow`.
- **Loan files across every state**:
  - a couple in `DRAFT` / `SUBMITTED`,
  - several `IN_REVIEW` with tasks at different points (some `PENDING_MAKER`,
    some `PENDING_CHECKER`, some `CHANGES_REQUESTED`, some tasks `COMPLETED`),
  - at least two with **some tasks overdue** (maker_submitted_at well in the past)
    so the dashboards show overdue counts,
  - two in `FUND_READY_TO_RELEASE`, one with `fund_ready_at` > 30 days ago so the
    next housekeeping run purges it live during a demo,
  - one already `PURGED` with an archive row.
- **`task_events`** rows consistent with each file's history so the activity feed
  and turnaround metrics look real.

Keep the numbers small enough to read on one dashboard screen (~12–15 files).
After changing the seeder, run it and eyeball `/dashboard/team` and
`/dashboard/loan-files`.
