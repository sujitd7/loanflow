from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.loan_file import LoanFile, LoanFileStatus
from app.models.task_event import TaskEvent
from app.models.user import User
from app.services import state_machine as sm


def _events(db: Session, loan_file_id: int) -> list[TaskEvent]:
    return list(
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.loan_file_id == loan_file_id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    )


def test_transition_draft_to_submitted_sets_timestamp_and_event(
    db: Session, make_loan_file: Callable[..., LoanFile], ops_maker: User
) -> None:
    loan_file = make_loan_file(created_by=ops_maker)

    sm.transition(db, loan_file, LoanFileStatus.SUBMITTED, actor=ops_maker)

    assert loan_file.status is LoanFileStatus.SUBMITTED
    assert loan_file.submitted_at is not None
    events = _events(db, loan_file.id)
    assert [e.action for e in events] == [sm.ACTION_LOAN_FILE_SUBMITTED]
    assert events[0].from_status == "DRAFT"
    assert events[0].to_status == "SUBMITTED"
    assert events[0].actor_id == ops_maker.id


def test_transition_rejects_skip_hop(
    db: Session, make_loan_file: Callable[..., LoanFile], ops_maker: User
) -> None:
    loan_file = make_loan_file(created_by=ops_maker)
    with pytest.raises(sm.IllegalTransition):
        sm.transition(db, loan_file, LoanFileStatus.IN_REVIEW, actor=ops_maker)
    assert loan_file.status is LoanFileStatus.DRAFT


def test_transition_rejects_backward(
    db: Session, make_loan_file: Callable[..., LoanFile], ops_maker: User
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.SUBMITTED)
    with pytest.raises(sm.IllegalTransition):
        sm.transition(db, loan_file, LoanFileStatus.DRAFT, actor=ops_maker)


def test_transition_purged_is_terminal(
    db: Session, make_loan_file: Callable[..., LoanFile], ops_maker: User
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.PURGED)
    with pytest.raises(sm.IllegalTransition):
        sm.transition(db, loan_file, LoanFileStatus.FUND_READY_TO_RELEASE, actor=ops_maker)


def test_illegal_transition_is_a_409() -> None:
    assert sm.IllegalTransition().status_code == 409


def test_entry_timestamp_is_set_once(
    db: Session, make_loan_file: Callable[..., LoanFile], ops_maker: User
) -> None:
    loan_file = make_loan_file(created_by=ops_maker)
    sm.transition(db, loan_file, LoanFileStatus.SUBMITTED, actor=ops_maker)
    first = loan_file.submitted_at
    # A re-entry (not reachable via the real graph, but the guard must hold).
    loan_file.status = LoanFileStatus.DRAFT
    sm.transition(db, loan_file, LoanFileStatus.SUBMITTED, actor=ops_maker)
    assert loan_file.submitted_at == first


def test_record_event_is_null_actor_safe_and_round_trips_payload(
    db: Session, make_loan_file: Callable[..., LoanFile]
) -> None:
    loan_file = make_loan_file()
    sm.record_event(
        db,
        loan_file,
        "CUSTOM",
        actor=None,
        payload={"a": 1, "nested": {"b": [2, 3]}},
    )
    count = db.scalar(
        select(func.count()).select_from(TaskEvent).where(TaskEvent.loan_file_id == loan_file.id)
    )
    assert count == 1
    event = _events(db, loan_file.id)[0]
    assert event.actor_id is None
    assert event.payload_json == {"a": 1, "nested": {"b": [2, 3]}}
