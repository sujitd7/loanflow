---
name: add-page
description: Add a screen to the LoanFlow React app the repo's way — feature folder, query hooks, route, four render states, test. Use for "add a page / screen / view".
---

# Add a page

Mirror an existing folder in `web/src/features/`.

1. **Feature folder** `web/src/features/<area>/`:
   - `api.ts` — TanStack Query hooks (`useXList`, `useX`, `useXMutation`). These
     are the only place Axios (`api` from `src/lib/http.ts`) is called.
     Mutations: `invalidateQueries` for what they touch; optimistic update +
     `onError` rollback for task actions.
   - `<Area>Page.tsx` — the screen. Handles **loading / empty / error+retry /
     data** explicitly.
   - Sub-components as needed, colocated.

2. **Types** — add to `web/src/lib/types.ts`, matching the API response schema.
   No `any`.

3. **Route** — wire into the router (`web/src/App.tsx` or `routes.tsx`):
   ```tsx
   <Route element={<RequireAuth />}>
     <Route element={<RequireRole roles={['UW_MAKER','UW_CHECKER']} />}>
       <Route path="/tasks" element={<TasksPage />} />
     </Route>
   </Route>
   ```
   Add a nav link if the role should see it.

4. **Forms** (if any) — react-hook-form + zod schema, inline errors, submit
   disabled while pending.

5. **Test** `<Area>Page.test.tsx` — RTL + MSW: assert loading, error+retry, empty,
   and a successful interaction. For mutations assert optimistic + rollback.

6. Run `npm run lint && npm run typecheck && npm test -- --run`.
