---
name: add-endpoint
description: Add a REST endpoint to the LoanFlow FastAPI service the repo's way — schema, router, service, RBAC, test, registration. Use when the task is "add an endpoint / route / API for X".
---

# Add an endpoint

Follow these steps in order. Read a sibling for the current style first
(`api/app/routers/loan_files.py` once it exists, else `health.py`).

1. **Schema** — `api/app/schemas/<area>.py`
   - `XCreate` / `XUpdate` for input, `XOut` for output (Pydantic v2,
     `model_config = ConfigDict(from_attributes=True)` on `XOut`).
   - Numeric bounds, enums, and string lengths belong here.

2. **Service** — `api/app/services/<area>.py`
   - Pure function(s) taking `db: Session` plus typed args; returns ORM objects.
   - Any status change calls `transition(db, obj, to_status, actor=...)`.
   - Raise `app.errors.NotFound` / `Conflict` / `Forbidden`, not `HTTPException`.

3. **Router** — `api/app/routers/<area>.py`
   - One `APIRouter(prefix="/<area>", tags=["<area>"])`.
   - Handlers: `db = Depends(get_db)`, `user = Depends(require_roles(Role.X, ...))`.
   - Thin: parse → call service → return schema. No business logic.
   - `response_model=XOut`, correct `status_code`.

4. **Register** — add `app.include_router(<area>.router)` in `api/app/main.py`.

5. **Errors** — confirm `app/errors.py` maps your exceptions to 404/409/403.

6. **Test** — `api/tests/test_<area>.py`
   - allowed role → 2xx; a forbidden role → 403; bad body → 422; missing → 404.
   - Use fixtures `client`, `db`, `auth_ops_maker`, `auth_uw_checker`, etc.

7. Run `docker compose run --rm api pytest -q api/tests/test_<area>.py` and
   `ruff check api` before committing.

If models changed, use the **add-migration** skill before finishing.
