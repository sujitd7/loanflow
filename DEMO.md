# Demo script (3 minutes)

_Filled in properly at P9. Outline:_

1. **The problem** (20s) — incoming loan files need independent verification before
   funds are released; four checks, each needs a maker and a separate checker.
2. **Submit a file** (30s) — log in as `ops.maker@demo.loanflow`, submit a loan
   file with documents. Show the 4 review tasks auto-created and assigned.
3. **Maker–checker** (60s) — log in as `uw.maker@demo.loanflow`, complete a check
   with findings. Log in as `uw.checker@demo.loanflow`, reject it (show it bounce
   back), then approve on the resubmit. Note you can't check your own work.
4. **Fund ready** (20s) — complete the remaining checks; the file flips to
   `FUND_READY_TO_RELEASE`.
5. **Housekeeping** (20s) — as `admin@demo.loanflow`, trigger
   `POST /admin/run-housekeeping`; the pre-seeded 31-day-old fund-ready file is
   purged to an archive row with no PII.
6. **Dashboards** (30s) — per-member task progress, per-file status funnel,
   overdue counts.
7. **Under the hood** (20s) — point at `docs/STATE_MACHINE.md`, the audit table,
   and `docs/ai-workflow.md`.

Demo logins (all password `demo1234`): `ops.maker`, `ops.checker`, `uw.maker`,
`uw.checker`, `admin` — all `@demo.loanflow`.
