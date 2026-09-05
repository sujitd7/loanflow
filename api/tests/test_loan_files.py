from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.errors import AppError, Conflict
from app.models.loan_document import LoanDocument
from app.models.loan_file import LoanFile, LoanFileStatus, ProductType
from app.models.review_task import CheckType, ReviewTask, ReviewTaskStatus
from app.models.task_event import TaskEvent
from app.models.user import Role, User
from app.services import loan_files as service
from tests.conftest import QueryCounter, TestingSessionLocal, engine

PDF_BYTES = b"%PDF-1.4\n%demo\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def _payload(**overrides: Any) -> dict[str, Any]:
    body = {
        "product_type": "TERM_LOAN",
        "loan_amount": "25000.00",
        "currency": "USD",
        "applicant_full_name": "Dana Applicant",
        "applicant_email": "dana@example.com",
    }
    body.update(overrides)
    return body


# --- create ----------------------------------------------------------------


def test_create_as_ops_maker_returns_201_draft(
    client: TestClient, auth_ops_maker: dict[str, str]
) -> None:
    resp = client.post("/loan-files", json=_payload(), headers=auth_ops_maker)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "DRAFT"
    assert body["loan_amount"] == "25000.00"
    assert body["task_total"] == 0


@pytest.mark.parametrize(
    "headers_fixture",
    ["auth_ops_checker", "auth_uw_maker", "auth_uw_checker", "auth_admin"],
)
def test_create_forbidden_for_non_ops_maker(
    client: TestClient, request: pytest.FixtureRequest, headers_fixture: str
) -> None:
    headers = request.getfixturevalue(headers_fixture)
    resp = client.post("/loan-files", json=_payload(), headers=headers)
    assert resp.status_code == 403


def test_create_requires_auth(client: TestClient) -> None:
    assert client.post("/loan-files", json=_payload()).status_code == 401


@pytest.mark.parametrize("amount", ["0.00", "-5.00"])
def test_create_rejects_non_positive_amount(
    client: TestClient, auth_ops_maker: dict[str, str], amount: str
) -> None:
    resp = client.post("/loan-files", json=_payload(loan_amount=amount), headers=auth_ops_maker)
    assert resp.status_code == 422


def test_create_rejects_bad_product_type(
    client: TestClient, auth_ops_maker: dict[str, str]
) -> None:
    resp = client.post(
        "/loan-files", json=_payload(product_type="CAMEL_LOAN"), headers=auth_ops_maker
    )
    assert resp.status_code == 422


def test_create_rejects_bad_email(client: TestClient, auth_ops_maker: dict[str, str]) -> None:
    resp = client.post(
        "/loan-files", json=_payload(applicant_email="not-an-email"), headers=auth_ops_maker
    )
    assert resp.status_code == 422


def test_create_writes_a_created_event(
    client: TestClient, db: Session, auth_ops_maker: dict[str, str]
) -> None:
    file_id = client.post("/loan-files", json=_payload(), headers=auth_ops_maker).json()["id"]
    events = db.scalars(select(TaskEvent).where(TaskEvent.loan_file_id == file_id)).all()
    assert [e.action for e in events] == ["LOAN_FILE_CREATED"]


# --- documents -----------------------------------------------------------


def _create_file(client: TestClient, headers: dict[str, str]) -> int:
    return int(client.post("/loan-files", json=_payload(), headers=headers).json()["id"])


def test_upload_pdf_ok(client: TestClient, db: Session, auth_ops_maker: dict[str, str]) -> None:
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        data={"kind": "IDENTITY"},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["byte_size"] == len(PDF_BYTES)
    assert body["kind"] == "IDENTITY"
    assert "storage_path" not in body
    stored = Path(settings.upload_dir) / str(file_id) / f"{body['sha256']}.pdf"
    assert stored.read_bytes() == PDF_BYTES


def test_upload_rejects_bad_content_type(
    client: TestClient, auth_ops_maker: dict[str, str]
) -> None:
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("x.exe", b"MZ...", "application/x-msdownload")},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 400


def test_upload_rejects_oversize(
    client: TestClient, auth_ops_maker: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.max_upload_bytes", 8)
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 400


def test_upload_rejects_content_type_spoof(
    client: TestClient, auth_ops_maker: dict[str, str]
) -> None:
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("evil.pdf", b"<html><script>alert(1)</script>", "application/pdf")},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 400


def test_upload_rejects_when_document_cap_reached(
    client: TestClient, auth_ops_maker: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.max_documents_per_file", 1)
    file_id = _create_file(client, auth_ops_maker)
    ok = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("a.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_ops_maker,
    )
    assert ok.status_code == 201
    over = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("b.pdf", PDF_BYTES + b" v2", "application/pdf")},
        headers=auth_ops_maker,
    )
    assert over.status_code == 409


def test_upload_rejects_empty_file(client: TestClient, auth_ops_maker: dict[str, str]) -> None:
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", b"", "application/pdf")},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 400


def test_upload_forbidden_for_uw_maker(
    client: TestClient, auth_ops_maker: dict[str, str], auth_uw_maker: dict[str, str]
) -> None:
    file_id = _create_file(client, auth_ops_maker)
    resp = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_uw_maker,
    )
    assert resp.status_code == 403


def test_upload_to_missing_file_404(client: TestClient, auth_ops_maker: dict[str, str]) -> None:
    resp = client.post(
        "/loan-files/999999/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_ops_maker,
    )
    assert resp.status_code == 404


def test_upload_same_bytes_twice_is_idempotent(
    client: TestClient, db: Session, auth_ops_maker: dict[str, str]
) -> None:
    file_id = _create_file(client, auth_ops_maker)
    first = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_ops_maker,
    ).json()
    second = client.post(
        f"/loan-files/{file_id}/documents",
        files={"file": ("app.pdf", PDF_BYTES, "application/pdf")},
        headers=auth_ops_maker,
    ).json()
    assert first["id"] == second["id"]
    count = db.scalar(select(func.count()).select_from(LoanFile).where(LoanFile.id == file_id))
    assert count == 1


def test_upload_after_submit_conflicts(
    client: TestClient,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    make_loan_file: Callable[..., LoanFile],
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.IN_REVIEW, documents=1)
    resp = client.post(
        f"/loan-files/{loan_file.id}/documents",
        files={"file": ("more.pdf", PDF_BYTES, "application/pdf")},
        headers=token_headers(ops_maker),
    )
    assert resp.status_code == 409


# --- submit (happy path via client) --------------------------------------


@pytest.fixture
def draft_with_doc(
    db: Session,
    ops_maker: User,
    make_loan_file: Callable[..., LoanFile],
) -> LoanFile:
    return make_loan_file(created_by=ops_maker, documents=1)


def test_submit_creates_exactly_four_tasks(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    resp = client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    assert resp.status_code == 200
    body = resp.json()
    assert body["file"]["status"] == "IN_REVIEW"
    assert body["file"]["submitted_at"] is not None
    assert body["file"]["task_total"] == 4

    tasks = db.scalars(select(ReviewTask).where(ReviewTask.loan_file_id == draft_with_doc.id)).all()
    assert {t.check_type for t in tasks} == set(CheckType)
    assert all(t.status is ReviewTaskStatus.PENDING_MAKER for t in tasks)
    assert all(t.version == 1 for t in tasks)


def test_submit_assignments_are_valid(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    maker_ids = {u.id for u in uw_makers}
    checker_ids = {u.id for u in uw_checkers}
    tasks = db.scalars(select(ReviewTask).where(ReviewTask.loan_file_id == draft_with_doc.id)).all()
    for task in tasks:
        assert task.maker_id in maker_ids
        assert task.checker_id in checker_ids
        assert task.maker_id != task.checker_id


def test_submit_round_robin_is_deterministic(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    by_type = {
        t.check_type: (t.maker_id, t.checker_id)
        for t in db.scalars(select(ReviewTask).where(ReviewTask.loan_file_id == draft_with_doc.id))
    }
    m = [u.id for u in uw_makers]
    c = [u.id for u in uw_checkers]
    assert by_type[CheckType.CREDIT_VALIDATION] == (m[0], c[0])
    assert by_type[CheckType.KYC_VERIFICATION] == (m[1], c[1])
    assert by_type[CheckType.PAYMENT_ELIGIBILITY] == (m[2], c[0])
    assert by_type[CheckType.TAX_RETURN_VERIFICATION] == (m[0], c[1])


def test_submit_writes_expected_event_sequence(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    client.post(
        f"/loan-files/{draft_with_doc.id}/documents",
        files={"file": ("a.pdf", PDF_BYTES, "application/pdf")},
        headers=token_headers(ops_maker),
    )
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    actions = [
        e.action
        for e in db.scalars(
            select(TaskEvent)
            .where(TaskEvent.loan_file_id == draft_with_doc.id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    ]
    assert actions == [
        "DOCUMENT_UPLOADED",
        "LOAN_FILE_SUBMITTED",
        "REVIEW_TASK_CREATED",
        "REVIEW_TASK_CREATED",
        "REVIEW_TASK_CREATED",
        "REVIEW_TASK_CREATED",
        "LOAN_FILE_IN_REVIEW",
    ]


# --- submit (guards & RBAC, HTTP status via client) ----------------------


def test_submit_without_documents_is_400(
    client: TestClient,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, documents=0)
    resp = client.post(f"/loan-files/{loan_file.id}/submit", headers=token_headers(ops_maker))
    assert resp.status_code == 400


def test_submit_forbidden_for_uw_checker(
    client: TestClient, draft_with_doc: LoanFile, auth_uw_checker: dict[str, str]
) -> None:
    resp = client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=auth_uw_checker)
    assert resp.status_code == 403


def test_submit_by_other_ops_maker_is_403(
    client: TestClient,
    draft_with_doc: LoanFile,
    make_user: Callable[..., User],
    token_headers: Callable[[User], dict[str, str]],
) -> None:
    other = make_user(Role.OPS_MAKER)
    resp = client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(other))
    assert resp.status_code == 403


def test_submit_missing_file_404(client: TestClient, auth_ops_maker: dict[str, str]) -> None:
    assert client.post("/loan-files/999999/submit", headers=auth_ops_maker).status_code == 404


@pytest.mark.parametrize("state", [LoanFileStatus.FUND_READY_TO_RELEASE, LoanFileStatus.PURGED])
def test_submit_from_terminal_states_conflicts(
    client: TestClient,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    make_loan_file: Callable[..., LoanFile],
    state: LoanFileStatus,
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=state, documents=1)
    resp = client.post(f"/loan-files/{loan_file.id}/submit", headers=token_headers(ops_maker))
    assert resp.status_code == 409


# --- submit rollback semantics (raw sessions) ---------------------------


def _seed_committed_draft(with_uw_makers: bool, with_uw_checkers: bool) -> tuple[int, int]:
    """Create a committed OPS_MAKER + draft-with-doc, return (file_id, actor_id)."""
    s = TestingSessionLocal()
    try:
        owner = User(
            email="owner-rollback@loanflow.dev",
            full_name="Owner",
            password_hash="x",
            role=Role.OPS_MAKER,
            team=None,
        )
        s.add(owner)
        s.flush()
        if with_uw_makers:
            s.add(
                User(
                    email="m@loanflow.dev",
                    full_name="M",
                    password_hash="x",
                    role=Role.UW_MAKER,
                    team=None,
                )
            )
        if with_uw_checkers:
            s.add(
                User(
                    email="c@loanflow.dev",
                    full_name="C",
                    password_hash="x",
                    role=Role.UW_CHECKER,
                    team=None,
                )
            )
        loan_file = LoanFile(
            status=LoanFileStatus.DRAFT,
            product_type=ProductType.TERM_LOAN,
            loan_amount=Decimal("1000.00"),
            currency="USD",
            applicant_full_name="A",
            applicant_email="a@example.com",
            created_by_id=owner.id,
        )
        s.add(loan_file)
        s.flush()
        s.add(
            LoanDocument(
                loan_file_id=loan_file.id,
                filename="d.pdf",
                content_type="application/pdf",
                byte_size=3,
                sha256="a" * 64,
                storage_path=f"{loan_file.id}/d.pdf",
                uploaded_by_id=owner.id,
            )
        )
        s.commit()
        return loan_file.id, owner.id
    finally:
        s.close()


@pytest.mark.parametrize("missing", ["makers", "checkers"])
def test_submit_without_uw_staff_rolls_back(missing: str) -> None:
    file_id, actor_id = _seed_committed_draft(
        with_uw_makers=(missing != "makers"),
        with_uw_checkers=(missing != "checkers"),
    )
    s = TestingSessionLocal()
    try:
        actor = s.get(User, actor_id)
        assert actor is not None
        with pytest.raises(Conflict):
            service.submit_loan_file(s, loan_file_id=file_id, actor=actor)
        s.rollback()
    finally:
        s.close()

    check = TestingSessionLocal()
    try:
        loan_file = check.get(LoanFile, file_id)
        assert loan_file is not None
        assert loan_file.status is LoanFileStatus.DRAFT
        assert loan_file.submitted_at is None
        task_count = check.scalar(
            select(func.count()).select_from(ReviewTask).where(ReviewTask.loan_file_id == file_id)
        )
        assert task_count == 0
        actions = check.scalars(
            select(TaskEvent.action).where(TaskEvent.loan_file_id == file_id)
        ).all()
        assert "LOAN_FILE_SUBMITTED" not in actions
    finally:
        check.close()


# --- submit idempotency -------------------------------------------------


def test_submit_twice_via_client_is_idempotent(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    headers = token_headers(ops_maker)
    first = client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=headers)
    second = client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=headers)
    assert first.status_code == second.status_code == 200

    first_ids = sorted(t["id"] for t in first.json()["tasks"])
    second_ids = sorted(t["id"] for t in second.json()["tasks"])
    assert first_ids == second_ids

    task_count = db.scalar(
        select(func.count())
        .select_from(ReviewTask)
        .where(ReviewTask.loan_file_id == draft_with_doc.id)
    )
    assert task_count == 4
    in_review_events = db.scalars(
        select(TaskEvent).where(
            TaskEvent.loan_file_id == draft_with_doc.id,
            TaskEvent.action == "LOAN_FILE_IN_REVIEW",
        )
    ).all()
    assert len(in_review_events) == 1


def test_submit_resumes_from_submitted_state(
    ops_maker: User,
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
    db: Session,
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.SUBMITTED, documents=1)
    db.commit()
    s = TestingSessionLocal()
    try:
        actor = s.get(User, ops_maker.id)
        assert actor is not None
        service.submit_loan_file(s, loan_file_id=loan_file.id, actor=actor)
        s.commit()
    finally:
        s.close()
    db.expire_all()
    refreshed = db.get(LoanFile, loan_file.id)
    assert refreshed is not None
    assert refreshed.status is LoanFileStatus.IN_REVIEW
    task_count = db.scalar(
        select(func.count()).select_from(ReviewTask).where(ReviewTask.loan_file_id == loan_file.id)
    )
    assert task_count == 4


def test_submit_creates_only_missing_tasks(
    ops_maker: User,
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
    db: Session,
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.SUBMITTED, documents=1)
    # pre-create two of the four checks
    for check_type in list(CheckType)[:2]:
        db.add(
            ReviewTask(
                loan_file_id=loan_file.id,
                check_type=check_type,
                status=ReviewTaskStatus.PENDING_MAKER,
                maker_id=uw_makers[0].id,
                checker_id=uw_checkers[0].id,
                version=1,
            )
        )
    db.commit()
    s = TestingSessionLocal()
    try:
        actor = s.get(User, ops_maker.id)
        assert actor is not None
        service.submit_loan_file(s, loan_file_id=loan_file.id, actor=actor)
        s.commit()
    finally:
        s.close()
    total = db.scalar(
        select(func.count()).select_from(ReviewTask).where(ReviewTask.loan_file_id == loan_file.id)
    )
    assert total == 4


# --- list ---------------------------------------------------------------


def test_list_has_no_n_plus_one(
    client: TestClient,
    db: Session,
    auth_admin: dict[str, str],
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
    assign_tasks: Callable[..., list[ReviewTask]],
) -> None:
    first = make_loan_file(documents=1)
    assign_tasks(first, uw_makers, uw_checkers)
    db.commit()
    with QueryCounter(engine) as counter:
        assert client.get("/loan-files", headers=auth_admin).status_code == 200
    baseline = len(counter.statements)

    for _ in range(6):
        extra = make_loan_file(documents=1)
        assign_tasks(extra, uw_makers, uw_checkers)
    db.commit()

    with QueryCounter(engine) as counter2:
        assert client.get("/loan-files", headers=auth_admin).status_code == 200
    assert len(counter2.statements) == baseline
    assert len(counter2.statements) <= 3


def test_list_pagination_and_total(
    client: TestClient,
    db: Session,
    auth_admin: dict[str, str],
    make_loan_file: Callable[..., LoanFile],
) -> None:
    for _ in range(5):
        make_loan_file()
    db.commit()
    resp = client.get("/loan-files?limit=2&offset=2", headers=auth_admin)
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 2


def test_list_filter_by_status(
    client: TestClient,
    db: Session,
    auth_admin: dict[str, str],
    make_loan_file: Callable[..., LoanFile],
) -> None:
    make_loan_file(status=LoanFileStatus.DRAFT)
    make_loan_file(status=LoanFileStatus.IN_REVIEW)
    db.commit()
    body = client.get("/loan-files?status=IN_REVIEW", headers=auth_admin).json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "IN_REVIEW"


def test_list_task_counts(
    client: TestClient,
    db: Session,
    auth_admin: dict[str, str],
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
    assign_tasks: Callable[..., list[ReviewTask]],
) -> None:
    loan_file = make_loan_file(status=LoanFileStatus.IN_REVIEW, documents=1)
    tasks = assign_tasks(loan_file, uw_makers, uw_checkers)
    tasks[0].status = ReviewTaskStatus.COMPLETED
    tasks[1].status = ReviewTaskStatus.COMPLETED
    db.commit()
    body = client.get("/loan-files?status=IN_REVIEW", headers=auth_admin).json()
    item = next(i for i in body["items"] if i["id"] == loan_file.id)
    assert item["task_total"] == 4
    assert item["task_completed"] == 2


def test_list_ops_maker_sees_only_own(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    make_user: Callable[..., User],
    make_loan_file: Callable[..., LoanFile],
) -> None:
    make_loan_file(created_by=ops_maker)
    make_loan_file(created_by=make_user(Role.OPS_MAKER))
    db.commit()
    body = client.get("/loan-files", headers=token_headers(ops_maker)).json()
    assert body["total"] == 1


def test_list_requires_auth(client: TestClient) -> None:
    assert client.get("/loan-files").status_code == 401


# --- detail -----------------------------------------------------------


def test_detail_returns_full_shape(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    body = client.get(f"/loan-files/{draft_with_doc.id}", headers=token_headers(ops_maker)).json()
    assert body["file"]["id"] == draft_with_doc.id
    assert len(body["documents"]) == 1
    assert len(body["tasks"]) == 4
    actions = [e["action"] for e in body["activity"]]
    assert actions[-1] == "LOAN_FILE_IN_REVIEW"
    assert body["activity"] == sorted(body["activity"], key=lambda e: e["created_at"])


def test_detail_404_for_missing(client: TestClient, auth_admin: dict[str, str]) -> None:
    assert client.get("/loan-files/999999", headers=auth_admin).status_code == 404


def test_detail_other_ops_maker_gets_404(
    client: TestClient,
    draft_with_doc: LoanFile,
    make_user: Callable[..., User],
    token_headers: Callable[[User], dict[str, str]],
) -> None:
    other = make_user(Role.OPS_MAKER)
    resp = client.get(f"/loan-files/{draft_with_doc.id}", headers=token_headers(other))
    assert resp.status_code == 404


def test_detail_uw_maker_without_a_task_gets_404(
    client: TestClient, draft_with_doc: LoanFile, auth_uw_maker: dict[str, str]
) -> None:
    resp = client.get(f"/loan-files/{draft_with_doc.id}", headers=auth_uw_maker)
    assert resp.status_code == 404


def test_detail_uw_maker_with_assigned_task_can_read(
    client: TestClient,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    # CREDIT_VALIDATION (index 0) is assigned to uw_makers[0].
    resp = client.get(f"/loan-files/{draft_with_doc.id}", headers=token_headers(uw_makers[0]))
    assert resp.status_code == 200


def test_list_uw_maker_sees_only_assigned_files(
    client: TestClient,
    db: Session,
    ops_maker: User,
    token_headers: Callable[[User], dict[str, str]],
    draft_with_doc: LoanFile,
    make_loan_file: Callable[..., LoanFile],
    uw_makers: list[User],
    uw_checkers: list[User],
) -> None:
    make_loan_file(documents=1)  # an unrelated file, no tasks
    client.post(f"/loan-files/{draft_with_doc.id}/submit", headers=token_headers(ops_maker))
    body = client.get("/loan-files", headers=token_headers(uw_makers[0])).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == draft_with_doc.id


# --- service-level guards ---------------------------------------------


def test_add_document_rejects_non_draft_directly(
    db: Session,
    ops_maker: User,
    make_loan_file: Callable[..., LoanFile],
) -> None:
    loan_file = make_loan_file(created_by=ops_maker, status=LoanFileStatus.SUBMITTED)
    with pytest.raises(Conflict):
        service.add_document(
            db,
            loan_file=loan_file,
            actor=ops_maker,
            filename="a.pdf",
            content_type="application/pdf",
            kind=None,
            data=PDF_BYTES,
        )


def test_add_document_rejects_bad_type_directly(
    db: Session,
    ops_maker: User,
    make_loan_file: Callable[..., LoanFile],
) -> None:
    loan_file = make_loan_file(created_by=ops_maker)
    with pytest.raises(AppError):
        service.add_document(
            db,
            loan_file=loan_file,
            actor=ops_maker,
            filename="a.txt",
            content_type="text/plain",
            kind=None,
            data=b"hello",
        )
