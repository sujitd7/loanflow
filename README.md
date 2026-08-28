# LoanFlow

A maker–checker loan-underwriting workbench. Operations logs an incoming loan file,
Underwriting runs four maker–checker verifications (credit, KYC, payment eligibility,
tax return), the file is marked **fund ready to release**, and a housekeeping job
purges it 30 days later.

Built to learn **React + TypeScript** (frontend) and **FastAPI + PostgreSQL**
(backend) end to end, deployed with a CI/CD pipeline, and to showcase a
guard-railed [Claude Code workflow](docs/ai-workflow.md).

Full plan: [`docs/ROADMAP.md`](docs/ROADMAP.md) · Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Stack

| Layer     | Choice                                        |
|-----------|-----------------------------------------------|
| Frontend  | React 18, TypeScript, Vite, TanStack Query    |
| Backend   | FastAPI, SQLAlchemy 2, Alembic                |
| Database  | PostgreSQL 16                                 |
| Jobs      | APScheduler worker process                    |
| Deploy    | Docker → Fly.io / single VPS                  |
| CI/CD     | GitHub Actions → GHCR                         |

## Run it locally

Prerequisites: Docker Desktop.

```bash
cp .env.example .env
docker compose up --build
```

| Service          | URL                          |
|------------------|------------------------------|
| Web (Vite)       | http://localhost:5173        |
| API (FastAPI)    | http://localhost:8000        |
| API docs         | http://localhost:8000/docs   |
| API health       | http://localhost:8000/health |
| Postgres         | localhost:5432               |

## Repo layout

```
api/      FastAPI service + Alembic migrations + pytest
worker/   APScheduler job runner (housekeeping / purge)
web/      React + TypeScript SPA (Vite)
infra/    deployment config (added in P8)
docs/     roadmap, architecture, ADRs, AI-workflow writeup
.claude/  committed Claude Code config: hooks, subagents, skills
scripts/  hook scripts and helpers
```

## Development

```bash
make help          # list tasks
make up / make down
make test          # api + web tests
make fmt / make lint
make migrate m="add users table"
```

## Status

Phase **P0 — Foundation & tooling**. See [`docs/STATUS.md`](docs/STATUS.md).
