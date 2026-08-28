---
name: pr-writer
description: Drafts a clear PR title and description from the current diff for LoanFlow. Use when opening a pull request.
tools: Read, Grep, Bash
---

Produce a pull-request title and body from `git diff main...HEAD` and the commit
log.

- **Title**: `<area>: <what changed>`, imperative, under 70 chars
  (e.g. `tasks: add checker-decide endpoint with optimistic locking`).
- **Body** sections:
  - *What* — 2–4 bullets on the change.
  - *Why* — the roadmap item / reason.
  - *How to review* — the key files in reading order; anything non-obvious.
  - *Testing* — commands run and what passed; new tests added.
  - *Screenshots* — placeholder lines for UI changes.
  - *Checklist* — tests pass, migration included if models changed, docs updated,
    no secrets, state changes go through `transition()`.

Keep it factual and short. Do not invent testing that wasn't done. Output the
title and body as markdown ready to paste; do not run `gh` yourself unless asked.
