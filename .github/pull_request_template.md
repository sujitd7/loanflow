## What

<!-- 2-4 bullets on the change -->

## Why

<!-- roadmap item / reason -->

## How to review

<!-- key files in reading order; anything non-obvious -->

## Testing

<!-- commands run + what passed; new tests added -->

## Checklist

- [ ] Tests pass (`make test`)
- [ ] Migration included if models changed, and `alembic downgrade -1` works
- [ ] State changes go through `transition()`
- [ ] Every new endpoint has an allowed-role and a forbidden-role test
- [ ] Docs updated (`docs/ROADMAP.md` ticked, ADR added if a decision was made)
- [ ] No secrets committed
