"""The single source of truth for status transitions.

Every loan-file status change goes through `transition()`; this is the only
module in the codebase permitted to assign a `.status` column (a hook enforces
that). Each transition appends exactly one `task_events` row via `record_event()`,
which is also the funnel for the handful of non-transition audit events.

P2 covers the loan-file half of the graph. P3 adds `transition_task()` for the
review-task maker/checker workflow.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..errors import Conflict
from ..models.loan_file import LoanFile, LoanFileStatus
from ..models.review_task import ReviewTask
from ..models.task_event import TaskEvent
from ..models.user import User

# --- audit vocabulary ------------------------------------------------------
ACTION_LOAN_FILE_CREATED = "LOAN_FILE_CREATED"
ACTION_LOAN_FILE_SUBMITTED = "LOAN_FILE_SUBMITTED"
ACTION_LOAN_FILE_IN_REVIEW = "LOAN_FILE_IN_REVIEW"
ACTION_DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
ACTION_REVIEW_TASK_CREATED = "REVIEW_TASK_CREATED"


class IllegalTransition(Conflict):
    detail = "Illegal state transition"


_LOAN_FILE_GRAPH: dict[LoanFileStatus, set[LoanFileStatus]] = {
    LoanFileStatus.DRAFT: {LoanFileStatus.SUBMITTED},
    LoanFileStatus.SUBMITTED: {LoanFileStatus.IN_REVIEW},
    LoanFileStatus.IN_REVIEW: {LoanFileStatus.FUND_READY_TO_RELEASE},
    LoanFileStatus.FUND_READY_TO_RELEASE: {LoanFileStatus.PURGED},
    LoanFileStatus.PURGED: set(),
}

_ENTRY_TIMESTAMP: dict[LoanFileStatus, str] = {
    LoanFileStatus.SUBMITTED: "submitted_at",
    LoanFileStatus.FUND_READY_TO_RELEASE: "fund_ready_at",
    LoanFileStatus.PURGED: "purged_at",
}

_DEFAULT_ACTION: dict[LoanFileStatus, str] = {
    LoanFileStatus.SUBMITTED: ACTION_LOAN_FILE_SUBMITTED,
    LoanFileStatus.IN_REVIEW: ACTION_LOAN_FILE_IN_REVIEW,
}


def transition(
    db: Session,
    loan_file: LoanFile,
    to_status: LoanFileStatus,
    *,
    actor: User | None,
    action: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    """Move `loan_file` to `to_status`, recording one audit event.

    Raises `IllegalTransition` (HTTP 409) if the hop is not on the graph.
    """
    from_status = loan_file.status
    if to_status not in _LOAN_FILE_GRAPH.get(from_status, set()):
        raise IllegalTransition(
            f"{from_status.value} -> {to_status.value} is not a permitted loan-file transition"
        )

    loan_file.status = to_status

    entry_ts = _ENTRY_TIMESTAMP.get(to_status)
    if entry_ts is not None and getattr(loan_file, entry_ts) is None:
        setattr(loan_file, entry_ts, datetime.now(UTC))

    return record_event(
        db,
        loan_file,
        action or _DEFAULT_ACTION.get(to_status, to_status.value),
        actor=actor,
        from_status=from_status.value,
        to_status=to_status.value,
        payload=payload,
    )


def record_event(
    db: Session,
    loan_file: LoanFile,
    action: str,
    *,
    actor: User | None,
    review_task: ReviewTask | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TaskEvent:
    """Append one `task_events` row. The only place task events are created."""
    event = TaskEvent(
        loan_file_id=loan_file.id,
        review_task_id=review_task.id if review_task is not None else None,
        actor_id=actor.id if actor is not None else None,
        action=action,
        from_status=from_status,
        to_status=to_status,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event
