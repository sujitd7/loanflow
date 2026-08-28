# infra/

Deployment configuration. Populated in **P8**.

Planned contents:
- `fly/` — `fly.toml` for `loanflow-api`, `loanflow-web`, `loanflow-worker`
  (or `compose.prod.yml` + `Caddyfile` for the single-VPS route)
- `.github/workflows/deploy.yml` lives at the repo root, not here
- notes on provisioning managed Postgres and setting secrets

See the `deploy` skill (`.claude/skills/deploy/SKILL.md`) for the release runbook.
