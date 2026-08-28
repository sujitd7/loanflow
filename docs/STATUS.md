# Status

**Phase:** P0 — Foundation & tooling (in progress)

Scaffold is in place: monorepo layout, docker-compose, health-check API + Vite
app, worker skeleton, pre-commit, `CLAUDE.md`, `.claude/` (hooks + 7 subagents +
6 skills), CI skeleton.

## Done
- Repo structure; git initialised; first commit on `main`
- FastAPI `/health` (checks DB) + Vite React app calling it
- APScheduler worker skeleton (no jobs yet)
- `.claude/` workflow config committed
- Verified locally: `ruff`, `mypy --strict`, `pytest` (api) and
  `tsc`, `eslint`, `vitest`, `vite build` (web) all green

## Next
- Create the GitHub repo, push, turn on branch protection for `main`
- Local dev: Docker Desktop is blocked on this machine (Intel VT-x disabled in
  BIOS + WSL2 not installed). Fix per `docs/LOCAL_DEV.md` Option A, or use the
  native workflow (Option B) with a free Neon Postgres in the meantime.
- Install host tooling so the hooks auto-run: `pip install ruff pre-commit`
  (Node is already present)
- Start **P1 — Identity, roles, RBAC** on a branch

See `docs/ROADMAP.md` for the full plan.
