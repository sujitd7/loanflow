# State machine

Single source of truth for status transitions. Enforced by `transition()` in
`api/app/services/state_machine.py` (added in P3). No code assigns a `status`
column directly — a hook flags it.

## Loan file

```
DRAFT ──submit──> SUBMITTED ──generate tasks──> IN_REVIEW ──all 4 tasks COMPLETED──> FUND_READY_TO_RELEASE ──+30d housekeeping──> PURGED
```

| From                    | To                      | Trigger                     | Guard |
|-------------------------|-------------------------|-----------------------------|-------|
| `DRAFT`                 | `SUBMITTED`             | OPS_MAKER submits           | ≥1 document; `loan_amount > 0`; valid `product_type` |
| `SUBMITTED`             | `IN_REVIEW`             | task generation             | exactly 4 `review_tasks` created + assigned in one transaction |
| `IN_REVIEW`             | `FUND_READY_TO_RELEASE` | last review task completes  | all 4 tasks `COMPLETED`; sets `fund_ready_at = now()` |
| `FUND_READY_TO_RELEASE` | `PURGED`                | housekeeping job            | `now() - fund_ready_at >= PURGE_AFTER_DAYS`; advisory lock held; sets `purged_at` |

`PURGED` is terminal. There is no un-submit; a file with a problem is handled by
rejecting its review tasks.

## Review task

```
PENDING_MAKER ──maker submits──> PENDING_CHECKER ──approve──> COMPLETED
      ^                                  │
      └────────── auto ──── CHANGES_REQUESTED <── reject ──┘
```

| From                | To                  | Trigger              | Guard |
|---------------------|---------------------|----------------------|-------|
| `PENDING_MAKER`     | `PENDING_CHECKER`   | maker submits        | actor `== maker_id`; `findings` non-empty; `version` matches |
| `PENDING_CHECKER`   | `COMPLETED`         | checker approves     | actor `== checker_id` and `!= maker_id`; `version` matches |
| `PENDING_CHECKER`   | `CHANGES_REQUESTED` | checker rejects      | actor `== checker_id`; `comment` non-empty; `version` matches |
| `CHANGES_REQUESTED` | `PENDING_MAKER`     | automatic on reject  | — (same transaction as the rejection) |

`COMPLETED` is terminal for the task.

## Invariants

1. `review_tasks.checker_id != review_tasks.maker_id` (DB check constraint).
2. A loan file is `FUND_READY_TO_RELEASE` **iff** its 4 tasks are all `COMPLETED`,
   and `fund_ready_at` is non-null exactly then.
3. Every transition appends one `task_events` row: `(actor_id, action,
   from_status, to_status, payload_json, created_at)`.
4. `version` is incremented on every task write; a mismatch → HTTP 409, client
   refetches and retries (optimistic locking).
5. `PURGED` files retain only a `loan_file_archive` row with **no PII**
   (`applicant_hash`, amounts, timestamps, outcome summary).

## The four check types

`CREDIT_VALIDATION`, `KYC_VERIFICATION`, `PAYMENT_ELIGIBILITY`,
`TAX_RETURN_VERIFICATION` — unique per loan file
(`UNIQUE(loan_file_id, check_type)`), which is also what makes `submit` idempotent.
