"""Loan-file intake: create a draft, attach documents, submit for review.

Pure functions over a `Session`. They raise `app.errors.*`, never
`HTTPException`, and never `db.commit()` — `get_db` commits once on success so a
failed submit leaves the file untouched. Status is changed only via
`state_machine.transition()`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ..config import settings
from ..errors import AppError, Conflict, Forbidden, NotFound
from ..models.loan_document import DocumentKind, LoanDocument
from ..models.loan_file import LoanFile, LoanFileStatus, ProductType
from ..models.review_task import CHECK_TYPE_ORDER, ReviewTask, ReviewTaskStatus
from ..models.task_event import TaskEvent
from ..models.user import Role, User
from ..schemas.loan_files import LoanFileCreate
from . import state_machine as sm

# Leading bytes each accepted upload type must start with. A file whose declared
# content-type is in this map but whose bytes do not match is rejected, so a
# renderable payload cannot masquerade as an allowed type.
_CONTENT_MAGIC: dict[str, tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF-",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}


@dataclass(frozen=True)
class LoanFileRow:
    loan_file: LoanFile
    task_total: int
    task_completed: int


@dataclass(frozen=True)
class LoanFileDetail:
    loan_file: LoanFile
    task_total: int
    task_completed: int
    documents: list[LoanDocument]
    tasks: list[ReviewTask]
    activity: list[TaskEvent]


def create_loan_file(db: Session, *, actor: User, data: LoanFileCreate) -> LoanFile:
    loan_file = LoanFile(
        product_type=data.product_type,
        loan_amount=data.loan_amount,
        currency=data.currency,
        applicant_full_name=data.applicant_full_name,
        applicant_email=str(data.applicant_email),
        applicant_dob=data.applicant_dob,
        notes=data.notes,
        created_by_id=actor.id,
    )
    db.add(loan_file)
    db.flush()
    sm.record_event(
        db,
        loan_file,
        sm.ACTION_LOAN_FILE_CREATED,
        actor=actor,
        to_status=LoanFileStatus.DRAFT.value,
        payload={"product_type": data.product_type.value, "loan_amount": str(data.loan_amount)},
    )
    return loan_file


def add_document(
    db: Session,
    *,
    loan_file: LoanFile,
    actor: User,
    filename: str,
    content_type: str,
    kind: DocumentKind | None,
    data: bytes,
) -> LoanDocument:
    if loan_file.status != LoanFileStatus.DRAFT:
        raise Conflict("Documents can only be added while the loan file is DRAFT")
    if content_type not in settings.allowed_upload_content_type_set:
        raise AppError("Unsupported document type")
    if not data:
        raise AppError("Uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise AppError(f"File exceeds the {settings.max_upload_bytes}-byte limit")
    expected = _CONTENT_MAGIC.get(content_type)
    if expected is not None and not data.startswith(expected):
        raise AppError("File contents do not match the declared type")

    digest = hashlib.sha256(data).hexdigest()
    existing = db.scalar(
        select(LoanDocument).where(
            LoanDocument.loan_file_id == loan_file.id, LoanDocument.sha256 == digest
        )
    )
    if existing is not None:
        return existing

    doc_count = db.scalar(
        select(func.count())
        .select_from(LoanDocument)
        .where(LoanDocument.loan_file_id == loan_file.id)
    )
    if doc_count and doc_count >= settings.max_documents_per_file:
        raise Conflict(f"A loan file may hold at most {settings.max_documents_per_file} documents")

    suffix = Path(filename).suffix.lower()[:10]
    rel_path = f"{loan_file.id}/{digest}{suffix}"
    dest = Path(settings.upload_dir) / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    document = LoanDocument(
        loan_file_id=loan_file.id,
        filename=Path(filename).name[:255] or "upload",
        content_type=content_type,
        byte_size=len(data),
        sha256=digest,
        storage_path=rel_path,
        kind=kind or DocumentKind.OTHER,
        uploaded_by_id=actor.id,
    )
    db.add(document)
    db.flush()
    sm.record_event(
        db,
        loan_file,
        sm.ACTION_DOCUMENT_UPLOADED,
        actor=actor,
        payload={
            "document_id": document.id,
            "filename": document.filename,
            "byte_size": document.byte_size,
        },
    )
    return document


def _active_uw(db: Session, role: Role) -> list[User]:
    return list(
        db.scalars(
            select(User).where(User.role == role, User.is_active.is_(True)).order_by(User.id)
        )
    )


def _assert_submittable(db: Session, loan_file: LoanFile) -> None:
    doc_count = db.scalar(
        select(func.count())
        .select_from(LoanDocument)
        .where(LoanDocument.loan_file_id == loan_file.id)
    )
    if not doc_count:
        raise AppError("At least one document is required before submitting")
    if loan_file.loan_amount is None or loan_file.loan_amount <= Decimal("0"):
        raise AppError("loan_amount must be greater than 0 to submit")
    # product_type is a non-null enum column, so validity is guaranteed by the schema.


def submit_loan_file(db: Session, *, loan_file_id: int, actor: User) -> LoanFile:
    loan_file = db.scalar(select(LoanFile).where(LoanFile.id == loan_file_id).with_for_update())
    if loan_file is None:
        raise NotFound("Loan file not found")

    if loan_file.created_by_id != actor.id:
        raise Forbidden("You can only submit loan files you created")

    if loan_file.status == LoanFileStatus.IN_REVIEW:
        return loan_file
    if loan_file.status == LoanFileStatus.DRAFT:
        _assert_submittable(db, loan_file)
        sm.transition(db, loan_file, LoanFileStatus.SUBMITTED, actor=actor)
    elif loan_file.status != LoanFileStatus.SUBMITTED:
        raise Conflict("Loan file has already progressed past review")

    _generate_review_tasks(db, loan_file, actor=actor)

    if loan_file.status == LoanFileStatus.SUBMITTED:
        tasks = list(db.scalars(select(ReviewTask).where(ReviewTask.loan_file_id == loan_file.id)))
        if len(tasks) != len(CHECK_TYPE_ORDER):  # pragma: no cover - guarded above
            raise Conflict("Expected exactly four review tasks after generation")
        sm.transition(
            db,
            loan_file,
            LoanFileStatus.IN_REVIEW,
            actor=actor,
            payload={"review_task_ids": sorted(t.id for t in tasks)},
        )

    db.flush()
    return loan_file


def _generate_review_tasks(db: Session, loan_file: LoanFile, *, actor: User) -> None:
    existing = {
        t.check_type
        for t in db.scalars(select(ReviewTask).where(ReviewTask.loan_file_id == loan_file.id))
    }
    missing = [ct for ct in CHECK_TYPE_ORDER if ct not in existing]
    if not missing:
        return

    makers = _active_uw(db, Role.UW_MAKER)
    checkers = _active_uw(db, Role.UW_CHECKER)
    if not makers:
        raise Conflict("Cannot submit: no active UW_MAKER users to assign")
    if not checkers:
        raise Conflict("Cannot submit: no active UW_CHECKER users to assign")

    new_tasks: list[ReviewTask] = []
    for check_type in missing:
        i = CHECK_TYPE_ORDER.index(check_type)
        maker = makers[i % len(makers)]
        checker = checkers[i % len(checkers)]
        # UW_MAKER and UW_CHECKER are disjoint sets (a user has exactly one role),
        # so maker and checker can never be the same person. The fallback below is
        # a defensive backstop for a future multi-role data model.
        if checker.id == maker.id:
            checker = checkers[(i + 1) % len(checkers)]
            if checker.id == maker.id:
                raise Conflict("Cannot assign a checker distinct from the maker")
        new_tasks.append(
            ReviewTask(
                loan_file_id=loan_file.id,
                check_type=check_type,
                status=ReviewTaskStatus.PENDING_MAKER,
                maker_id=maker.id,
                checker_id=checker.id,
                version=1,
            )
        )

    db.add_all(new_tasks)
    try:
        db.flush()
    except IntegrityError as exc:
        # Almost certainly the UNIQUE(loan_file_id, check_type) backstop firing
        # because a concurrent submit generated the tasks first. The failed flush
        # has poisoned the transaction, so unwind it; the client retries and the
        # replay path returns the now-IN_REVIEW file.
        db.rollback()
        raise Conflict("Review tasks for this loan file already exist; retry") from exc

    for task in new_tasks:
        sm.record_event(
            db,
            loan_file,
            sm.ACTION_REVIEW_TASK_CREATED,
            actor=actor,
            review_task=task,
            to_status=ReviewTaskStatus.PENDING_MAKER.value,
            payload={
                "review_task_id": task.id,
                "check_type": task.check_type.value,
                "maker_id": task.maker_id,
                "checker_id": task.checker_id,
            },
        )


def _visible_filters(actor: User) -> list[ColumnElement[bool]]:
    """Restrict a loan-file query to what `actor` may see.

    - ADMIN / OPS_CHECKER: everything (oversight roles).
    - OPS_MAKER: only files they created.
    - UW_MAKER / UW_CHECKER: only files carrying a review task assigned to them.
    """
    if actor.role in (Role.ADMIN, Role.OPS_CHECKER):
        return []
    if actor.role == Role.OPS_MAKER:
        return [LoanFile.created_by_id == actor.id]
    assignee = ReviewTask.maker_id if actor.role == Role.UW_MAKER else ReviewTask.checker_id
    return [
        exists().where(
            ReviewTask.loan_file_id == LoanFile.id,
            assignee == actor.id,
        )
    ]


def _actor_can_see(db: Session, loan_file: LoanFile, actor: User) -> bool:
    if actor.role in (Role.ADMIN, Role.OPS_CHECKER):
        return True
    if actor.role == Role.OPS_MAKER:
        return loan_file.created_by_id == actor.id
    assignee = ReviewTask.maker_id if actor.role == Role.UW_MAKER else ReviewTask.checker_id
    return bool(
        db.scalar(
            select(
                exists().where(
                    ReviewTask.loan_file_id == loan_file.id,
                    assignee == actor.id,
                )
            )
        )
    )


def list_loan_files(
    db: Session,
    *,
    actor: User,
    status: LoanFileStatus | None = None,
    product_type: ProductType | None = None,
    created_by_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[LoanFileRow], int]:
    filters: list[ColumnElement[bool]] = _visible_filters(actor)
    if status is not None:
        filters.append(LoanFile.status == status)
    if product_type is not None:
        filters.append(LoanFile.product_type == product_type)
    if created_by_id is not None:
        filters.append(LoanFile.created_by_id == created_by_id)

    agg = (
        select(
            ReviewTask.loan_file_id.label("lf_id"),
            func.count().label("task_total"),
            func.count()
            .filter(ReviewTask.status == ReviewTaskStatus.COMPLETED)
            .label("task_completed"),
        )
        .group_by(ReviewTask.loan_file_id)
        .subquery()
    )

    stmt = (
        select(
            LoanFile,
            func.coalesce(agg.c.task_total, 0),
            func.coalesce(agg.c.task_completed, 0),
        )
        .outerjoin(agg, agg.c.lf_id == LoanFile.id)
        .where(*filters)
        .order_by(LoanFile.created_at.desc(), LoanFile.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = [
        LoanFileRow(loan_file=lf, task_total=int(total), task_completed=int(done))
        for lf, total, done in db.execute(stmt).all()
    ]
    total_count = db.scalar(select(func.count()).select_from(LoanFile).where(*filters)) or 0
    return rows, int(total_count)


def get_loan_file(db: Session, *, loan_file_id: int, actor: User) -> LoanFile:
    """Load a loan file the actor is allowed to see, else raise ``NotFound``."""
    loan_file = db.get(LoanFile, loan_file_id)
    if loan_file is None:
        raise NotFound("Loan file not found")
    if not _actor_can_see(db, loan_file, actor):
        raise NotFound("Loan file not found")
    return loan_file


def get_loan_file_detail(db: Session, *, loan_file_id: int, actor: User) -> LoanFileDetail:
    loan_file = get_loan_file(db, loan_file_id=loan_file_id, actor=actor)

    documents = list(
        db.scalars(
            select(LoanDocument)
            .where(LoanDocument.loan_file_id == loan_file_id)
            .order_by(LoanDocument.id)
        )
    )
    tasks = list(
        db.scalars(
            select(ReviewTask)
            .where(ReviewTask.loan_file_id == loan_file_id)
            .order_by(ReviewTask.check_type)
        )
    )
    activity = list(
        db.scalars(
            select(TaskEvent)
            .where(TaskEvent.loan_file_id == loan_file_id)
            .order_by(TaskEvent.created_at, TaskEvent.id)
        )
    )
    completed = sum(1 for t in tasks if t.status == ReviewTaskStatus.COMPLETED)
    return LoanFileDetail(
        loan_file=loan_file,
        task_total=len(tasks),
        task_completed=completed,
        documents=documents,
        tasks=tasks,
        activity=activity,
    )
