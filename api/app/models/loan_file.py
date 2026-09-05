import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, TimestampMixin

if TYPE_CHECKING:
    from .loan_document import LoanDocument
    from .review_task import ReviewTask
    from .task_event import TaskEvent


class LoanFileStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "IN_REVIEW"
    FUND_READY_TO_RELEASE = "FUND_READY_TO_RELEASE"
    PURGED = "PURGED"


class ProductType(str, enum.Enum):
    TERM_LOAN = "TERM_LOAN"
    LINE_OF_CREDIT = "LINE_OF_CREDIT"
    MORTGAGE = "MORTGAGE"
    AUTO_LOAN = "AUTO_LOAN"
    PERSONAL_LOAN = "PERSONAL_LOAN"


class LoanFile(Base, TimestampMixin):
    """A loan application moving through intake, review and release.

    `status` is written only by `transition()` in
    `api/app/services/state_machine.py` — never assigned directly.
    """

    __tablename__ = "loan_files"
    __table_args__ = (
        CheckConstraint("loan_amount >= 0", name="ck_loan_files_amount_nonneg"),
        Index("ix_loan_files_status_fund_ready_at", "status", "fund_ready_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[LoanFileStatus] = mapped_column(
        Enum(LoanFileStatus, name="loan_file_status"),
        default=LoanFileStatus.DRAFT,
        server_default=LoanFileStatus.DRAFT.value,
    )
    product_type: Mapped[ProductType] = mapped_column(Enum(ProductType, name="product_type"))
    loan_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), server_default="USD")

    applicant_full_name: Mapped[str] = mapped_column(String(200))
    applicant_email: Mapped[str] = mapped_column(String(320))
    applicant_dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fund_ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["LoanDocument"]] = relationship(
        back_populates="loan_file", cascade="all, delete-orphan", passive_deletes=True
    )
    review_tasks: Mapped[list["ReviewTask"]] = relationship(
        back_populates="loan_file", cascade="all, delete-orphan", passive_deletes=True
    )
    events: Mapped[list["TaskEvent"]] = relationship(
        back_populates="loan_file", cascade="all, delete-orphan", passive_deletes=True
    )
