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
- Verify `docker compose up` is green end to end (needs Docker Desktop)
- Install host tooling so the hooks auto-run: `pip install ruff pre-commit`
  (Node is already present)
- Start **P1 — Identity, roles, RBAC** on a branch

See `docs/ROADMAP.md` for the full plan.
