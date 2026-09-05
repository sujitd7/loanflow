from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..models.loan_document import DocumentKind
from ..models.loan_file import LoanFileStatus, ProductType
from ..models.review_task import CheckType, ReviewTaskStatus


class LoanFileCreate(BaseModel):
    product_type: ProductType
    loan_amount: Decimal = Field(gt=0, le=Decimal("100_000_000"), max_digits=14, decimal_places=2)
    currency: str = Field("USD", pattern="^(USD|EUR|GBP)$")
    applicant_full_name: str = Field(min_length=1, max_length=200)
    applicant_email: EmailStr
    applicant_dob: date | None = None
    notes: str | None = Field(None, max_length=2000)


class LoanFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: LoanFileStatus
    product_type: ProductType
    loan_amount: Decimal
    currency: str
    applicant_full_name: str
    applicant_email: EmailStr
    applicant_dob: date | None
    notes: str | None
    created_by_id: int
    submitted_at: datetime | None
    fund_ready_at: datetime | None
    created_at: datetime
    updated_at: datetime
    task_total: int = 0
    task_completed: int = 0


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    loan_file_id: int
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    kind: DocumentKind | None
    uploaded_by_id: int
    created_at: datetime


class ReviewTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    loan_file_id: int
    check_type: CheckType
    status: ReviewTaskStatus
    maker_id: int
    checker_id: int
    version: int
    findings: str | None
    checker_comment: str | None
    completed_at: datetime | None
    created_at: datetime


class TaskEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    loan_file_id: int
    review_task_id: int | None
    actor_id: int | None
    action: str
    from_status: str | None
    to_status: str | None
    payload_json: dict[str, Any] | None
    created_at: datetime


class LoanFilePage(BaseModel):
    items: list[LoanFileOut]
    total: int
    limit: int
    offset: int


class LoanFileDetailOut(BaseModel):
    file: LoanFileOut
    documents: list[DocumentOut]
    tasks: list[ReviewTaskOut]
    activity: list[TaskEventOut]
