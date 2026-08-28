---
name: deploy
description: The LoanFlow release runbook — how a change reaches production, how to verify it, and how to roll back. Use when deploying, checking a deploy, or recovering from a bad one.
---

# Deploy runbook

Production = three containers (`api`, `web`, `worker`) + managed Postgres.
**Normal releases happen only through CI on `main`** — you do not run `fly deploy`
by hand (a hook blocks it off `main`).

## Normal path

1. Merge the PR to `main` after checks are green.
2. GitHub Actions (`.github/workflows/deploy.yml`) then:
   - builds and pushes `ghcr.io/<owner>/loanflow-{api,web,worker}:<sha>`,
   - deploys the new images,
   - runs `alembic upgrade head` as a release step (migrations are
     backward-compatible, so this is safe before traffic shifts),
   - smoke-tests `GET /health` (expect 200) and `GET /` on web,
   - on any failure, keeps the previous release and reports.
3. Watch the Actions run. After green, hit the live `/health` and click through
   one maker→checker action.

## Verify

- `GET https://<api-host>/health` → `{"status":"ok","db":"ok"}`
- API docs load at `/docs`
- Log in as `admin@demo.loanflow` and load both dashboards

## Rollback

Migrations are expand/contract, so rolling code back does not require a DB
rollback.

- **Fly:** `fly releases -a loanflow-api` → `fly deploy -a loanflow-api --image ghcr.io/<owner>/loanflow-api:<previous-sha>` (repeat for web/worker).
- **VPS:** set the image tags back to the previous sha in the compose file and
  `docker compose pull && docker compose up -d`.
- If a migration itself is the problem, apply its `downgrade` deliberately:
  `alembic downgrade -1` — only if that revision's downgrade is known-good.

## Secrets

`fly secrets set KEY=value -a <app>` (or the host's env file). Never in the repo,
never baked into an image layer. Rotate `JWT_SECRET` by adding the new one as a
second accepted key for one release, then removing the old.
