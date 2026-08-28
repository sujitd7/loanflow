# Status

**Phase:** P1 — Identity, roles, RBAC (complete — PR #1, CI green, awaiting merge)

## Done
- **P0** — monorepo scaffold, docker-compose, `/health` API + Vite app, worker
  skeleton, `.claude/` workflow config, CI skeleton, `git init`.
- **P1** — identity layer:
  - `users` + `refresh_tokens` models, Alembic migration `bd693f8a6bb0`
  - Argon2 password hashing + JWT access/refresh in `app/security.py`
  - `POST /auth/login`, `POST /auth/refresh` (rotating, with reuse detection that
    burns the token family), `POST /auth/logout`, `GET /auth/me`
  - `Role` / `Team` enums; `require_roles(...)` RBAC dependency in `app/deps.py`
  - `app/errors.py` — `AppError` hierarchy + handler wired in `create_app()`
  - conftest: `make_user` factory, per-role user + `auth_*` header fixtures,
    test-only `/_probe/*` routes
  - `tests/test_auth.py` + `tests/test_config.py` — login ok/bad/inactive,
    expired + wrong-type tokens, rotation + reuse, logout ownership, per-role
    probe matrix, JWT-secret boot guard (35 tests, green on CI Postgres)
  - `security-reviewer` pass drove the hardening (reuse-burn committed
    independently, secret fail-fast, row-locked rotation, timing, claim checks)

## Deferred from P0 (infra, not blocking)
- GitHub repo + branch protection on `main`.
- `docker compose up` verification — Docker is blocked on this machine
  (`docs/LOCAL_DEV.md`). Backend tests run on the SQLite fallback locally; CI
  uses a real Postgres service. Migration round-trip is verified there.

## Next
- Merge the P1 PR.
- Start **P2 — Loan-file intake + task generation** on a branch.

See `docs/ROADMAP.md` for the full plan.
