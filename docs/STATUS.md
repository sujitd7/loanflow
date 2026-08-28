# Status

**Phase:** P0 — Foundation & tooling (in progress)

Scaffold is in place: monorepo layout, docker-compose, health-check API + Vite
app, worker skeleton, pre-commit, `CLAUDE.md`, `.claude/` (hooks + 7 subagents +
6 skills), CI skeleton.

## Done
- Repo structure and `docker compose up` bring-up
- FastAPI `/health` (checks DB), Vite React app calling it
- APScheduler worker skeleton (no jobs yet)
- `.claude/` workflow config committed

## Next
- Initialise git, push to GitHub, turn on branch protection
- Verify `docker compose up` is green end to end on your machine
- Install host tooling so the hooks are active: `pip install ruff pre-commit`,
  Node already present
- Start **P1 — Identity, roles, RBAC** on a branch

See `docs/ROADMAP.md` for the full plan.
