from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import require_roles
from ..errors import AppError
from ..models.loan_document import DocumentKind
from ..models.loan_file import LoanFileStatus, ProductType
from ..models.user import Role, User
from ..schemas.loan_files import (
    DocumentOut,
    LoanFileCreate,
    LoanFileDetailOut,
    LoanFileOut,
    LoanFilePage,
    ReviewTaskOut,
    TaskEventOut,
)
from ..services import loan_files as service
from ..services.loan_files import LoanFileDetail

router = APIRouter(prefix="/loan-files", tags=["loan-files"])

_READERS = (
    Role.OPS_MAKER,
    Role.OPS_CHECKER,
    Role.UW_MAKER,
    Role.UW_CHECKER,
    Role.ADMIN,
)


def _file_out(loan_file: object, task_total: int, task_completed: int) -> LoanFileOut:
    out = LoanFileOut.model_validate(loan_file)
    out.task_total = task_total
    out.task_completed = task_completed
    return out


def _detail_out(detail: LoanFileDetail) -> LoanFileDetailOut:
    return LoanFileDetailOut(
        file=_file_out(detail.loan_file, detail.task_total, detail.task_completed),
        documents=[DocumentOut.model_validate(d) for d in detail.documents],
        tasks=[ReviewTaskOut.model_validate(t) for t in detail.tasks],
        activity=[TaskEventOut.model_validate(e) for e in detail.activity],
    )


@router.post("", response_model=LoanFileOut, status_code=status.HTTP_201_CREATED)
def create_loan_file(
    body: LoanFileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPS_MAKER)),
) -> LoanFileOut:
    loan_file = service.create_loan_file(db, actor=user, data=body)
    return _file_out(loan_file, 0, 0)


@router.post(
    "/{loan_file_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    loan_file_id: int,
    file: UploadFile = File(...),
    kind: DocumentKind | None = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPS_MAKER)),
) -> DocumentOut:
    loan_file = service.get_loan_file(db, loan_file_id=loan_file_id, actor=user)
    cap = settings.max_upload_bytes
    raw = file.file.read(cap + 1)
    if len(raw) > cap:
        raise AppError(f"File exceeds the {cap}-byte limit")
    document = service.add_document(
        db,
        loan_file=loan_file,
        actor=user,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        kind=kind,
        data=raw,
    )
    return DocumentOut.model_validate(document)


@router.post("/{loan_file_id}/submit", response_model=LoanFileDetailOut)
def submit_loan_file(
    loan_file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.OPS_MAKER)),
) -> LoanFileDetailOut:
    service.submit_loan_file(db, loan_file_id=loan_file_id, actor=user)
    detail = service.get_loan_file_detail(db, loan_file_id=loan_file_id, actor=user)
    return _detail_out(detail)


@router.get("", response_model=LoanFilePage)
def list_loan_files(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_READERS)),
    status: LoanFileStatus | None = None,
    product_type: ProductType | None = None,
    created_by_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> LoanFilePage:
    rows, total = service.list_loan_files(
        db,
        actor=user,
        status=status,
        product_type=product_type,
        created_by_id=created_by_id,
        limit=limit,
        offset=offset,
    )
    return LoanFilePage(
        items=[_file_out(r.loan_file, r.task_total, r.task_completed) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{loan_file_id}", response_model=LoanFileDetailOut)
def get_loan_file(
    loan_file_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*_READERS)),
) -> LoanFileDetailOut:
    detail = service.get_loan_file_detail(db, loan_file_id=loan_file_id, actor=user)
    return _detail_out(detail)
