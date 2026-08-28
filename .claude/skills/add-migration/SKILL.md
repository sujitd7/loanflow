---
name: add-migration
description: Create and verify an Alembic migration for LoanFlow after a model change. Use whenever anything under api/app/models/ is added or altered.
---

# Add a migration

1. **Autogenerate**
   ```
   docker compose run --rm api alembic revision --autogenerate -m "short message"
   ```
   New file lands in `api/alembic/versions/`.

2. **Review the generated file — autogenerate is not trustworthy.** Check by hand:
   - Only the intended change is present (no stray drops from an out-of-date DB).
   - `server_default` for new non-null columns, or a two-step add + backfill.
   - `CHECK` constraints, enum value changes, unique constraints, named indexes.
   - A correct, tested `downgrade()`.

3. **Destructive change?** If it drops a column/table or narrows a type, split it:
   add-new → deploy → backfill → switch reads → drop-old in a later migration.
   Backward-compatible migrations are what make CD rollbacks safe.

4. **Verify round-trip**
   ```
   docker compose run --rm api alembic upgrade head
   docker compose run --rm api alembic downgrade -1
   docker compose run --rm api alembic upgrade head
   docker compose run --rm api alembic check
   ```

5. Commit the migration **with** the model change in the same PR.

Never edit a migration that has run on a shared environment — add a new one.
