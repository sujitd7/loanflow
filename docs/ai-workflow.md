# How this project was built with Claude Code

A deliberate, guard-railed AI workflow — not "I pasted code from a chatbot". The
config below is committed in `.claude/` and `scripts/hooks/`. Fill the
**Evidence** sections with real screenshots / transcripts as you build.

## The setup

| Piece | Where | What it does |
|-------|-------|--------------|
| Project brief | `CLAUDE.md` | Stack, run commands, repo map, conventions, the "never write `.status` directly" rule, RBAC matrix. Loaded every session. |
| Hooks | `.claude/settings.json` + `scripts/hooks/` | Auto-format/lint on write; block dangerous Bash; flag raw status writes; optional test-run on Stop; print status on session start. |
| Subagents | `.claude/agents/*.md` | 7 focused reviewers/builders: `api-designer`, `db-migrator`, `workflow-modeler`, `security-reviewer`, `frontend-builder`, `test-writer`, `pr-writer`. |
| Skills | `.claude/skills/*/SKILL.md` | Repo-specific recipes: `add-endpoint`, `add-migration`, `add-scheduled-job`, `add-page`, `seed-demo-data`, `deploy`. |
| Agentic loop | `/loop` | Works `docs/ROADMAP.md` one checkbox at a time, tests first. |

## Hooks

- **`guard_bash.py`** (PreToolUse) — refuses `rm -rf /`, force-push without lease,
  `docker compose down -v`, `fly deploy`, prod `psql`. Exit 2 blocks the command.
- **`format_file.py`** (PostToolUse) — runs `ruff format` + `ruff check --fix` on
  Python, prettier/eslint on web files, right after each edit.
- **`guard_state_machine.py`** (PostToolUse) — greps the just-edited router/service
  for `obj.status = ...` and pushes back, keeping all transitions in
  `transition()`.
- **`stop_tests.py`** (Stop, opt-in via `LOANFLOW_TEST_ON_STOP=1`) — runs the
  backend suite; a red suite means the loop is not "done".
- **`session_status.py`** (SessionStart) — prints `docs/STATUS.md`, the git
  branch, and the next roadmap item.

**Evidence:** _paste a terminal shot of `guard_bash.py` blocking a command, and
one of `format_file.py` reformatting a file._

## Subagents in practice

Typical feature flow for an endpoint:
1. `api-designer` drafts schema + router + service + tests to repo conventions.
2. `db-migrator` produces and round-trip-tests the Alembic migration.
3. `workflow-modeler` checks any transition change keeps the graph total.
4. `security-reviewer` reviews the diff for authz/RBAC holes.
5. `test-writer` fills edge cases.
6. `pr-writer` drafts the PR.

**Evidence:** _link a PR where `security-reviewer` caught a real object-level
access bug, with its output quoted._

## The agentic loop

```
/loop implement the next unchecked item in docs/ROADMAP.md —
write the tests first, make them pass, run the suite,
tick the checkbox, and commit with a conventional message
```

The Stop hook (with `LOANFLOW_TEST_ON_STOP=1`) is what makes this safe to leave
running: it won't declare a step finished while tests fail.

**Evidence:** _screenshot one loop iteration: failing test → implementation →
green → commit._

## What was delegated vs. kept

- **Delegated:** boilerplate (routers, schemas, fixtures, migrations), test
  scaffolding, formatting, PR text, first-draft SQL for the dashboards.
- **Kept:** the domain model and state machine, the RBAC matrix, the
  APScheduler-over-Celery call (ADR 0002), the expand/contract migration
  discipline, and every review decision.
