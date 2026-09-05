# Status

**Phase:** P2 — Loan-file intake + task generation (complete on branch
`p2-loan-file-intake`, tests green — awaiting review + PR)

## Done
- **P0** — monorepo scaffold, docker-compose, `/health` API + Vite app, worker
  skeleton, `.claude/` workflow config, CI skeleton, `git init`.
- **P1** — identity layer: `users` + `refresh_tokens`, Argon2 + rotating JWT with
  reuse-burn, `/auth/*`, `Role`/`Team` enums, `require_roles(...)`, `AppError`
  hierarchy, per-role test fixtures. Merged (PR #1).
- **P2** — loan-file intake:
  - `loan_files`, `loan_documents`, `review_tasks` (incl. `version`),
    `task_events` models + migration `f81705c85836` (round-trip + `alembic check`
    verified on SQLite; CI verifies on Postgres)
  - `app/services/state_machine.py` — `transition()` (loan-file graph only) +
    `record_event()`; the single writer of a `status` column
  - `POST /loan-files` (OPS_MAKER), `POST /loan-files/{id}/documents` (multipart,
    size/type limits, sha256 dedup, id-derived storage path),
    `POST /loan-files/{id}/submit` (atomic: DRAFT→SUBMITTED, generate 4
    round-robin-assigned review tasks, SUBMITTED→IN_REVIEW; idempotent via
    `UNIQUE(loan_file_id, check_type)` + status dispatch + `FOR UPDATE`)
  - `GET /loan-files` (pagination + status/product/creator filter + per-file task
    counts in 2 queries, N+1-guarded by a test), `GET /loan-files/{id}` (file +
    documents + tasks + activity feed)
  - reads open to all roles; `OPS_MAKER` scoped to their own files (404 on others)
  - `tests/test_state_machine.py` + `tests/test_loan_files.py` — ~53 new tests
    incl. idempotent submit (client + raw-session), staffing-failure rollback,
    round-robin determinism, N+1 guard

## Deferred / not blocking
- GitHub repo + branch protection on `main`.
- `docker compose up` verification — Docker blocked on this machine
  (`docs/LOCAL_DEV.md`). Backend tests run on the SQLite fallback locally; CI
  uses a real Postgres service.
- `SELECT ... FOR UPDATE` is a no-op on SQLite — the concurrency serialisation is
  only exercised on CI Postgres.

## Review outcome (P2)
- `workflow-modeler`: **PASS** on state-machine correctness.
- `security-reviewer`: read scoping tightened to the RBAC matrix (UW roles now
  see only files they hold a task on); added upload magic-byte sniffing, a
  per-file document cap, `loan_amount` ceiling + currency allow-list; dropped
  `storage_path` from the API response; static upload error messages.

## Carry into P3 (from the reviews)
- The `IN_REVIEW → FUND_READY_TO_RELEASE` rollup needs the same
  `SELECT ... FOR UPDATE` on `loan_files` that `submit_loan_file` uses — two
  checkers completing the last two tasks concurrently otherwise race.
- Add `ACTION_*` constants for the `FUND_READY_TO_RELEASE` / `PURGED` transitions
  when P3/P4 wire them.
- `_generate_review_tasks` calls `db.rollback()` directly on `IntegrityError`;
  keep that pattern contained — don't compose `submit_loan_file` into a larger
  unit of work without revisiting it.
- The `+1` checker fallback in `_generate_review_tasks` is unreachable while users
  have exactly one role; revisit if the role model ever goes multi-valued.

## Next
- Open the P2 PR.
- Start **P3 — Maker–checker flow** (`transition_task()`, `/tasks/*` endpoints,
  FUND_READY rollup).

See `docs/ROADMAP.md` for the full plan.
