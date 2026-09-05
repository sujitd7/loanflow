import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, TimestampMixin

if TYPE_CHECKING:
    from .loan_file import LoanFile


class ReviewTaskStatus(str, enum.Enum):
    PENDING_MAKER = "PENDING_MAKER"
    PENDING_CHECKER = "PENDING_CHECKER"
    COMPLETED = "COMPLETED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class CheckType(str, enum.Enum):
    CREDIT_VALIDATION = "CREDIT_VALIDATION"
    KYC_VERIFICATION = "KYC_VERIFICATION"
    PAYMENT_ELIGIBILITY = "PAYMENT_ELIGIBILITY"
    TAX_RETURN_VERIFICATION = "TAX_RETURN_VERIFICATION"


#: The four checks generated for every submitted loan file, in assignment order.
CHECK_TYPE_ORDER: tuple[CheckType, ...] = (
    CheckType.CREDIT_VALIDATION,
    CheckType.KYC_VERIFICATION,
    CheckType.PAYMENT_ELIGIBILITY,
    CheckType.TAX_RETURN_VERIFICATION,
)


class ReviewTask(Base, TimestampMixin):
    """One maker-checker review of a single aspect of a loan file.

    `status` is written only by the state machine. The maker/checker workflow
    lands in P3; P2 only creates rows in `PENDING_MAKER`.
    """

    __tablename__ = "review_tasks"
    __table_args__ = (
        CheckConstraint("checker_id <> maker_id", name="ck_review_tasks_checker_ne_maker"),
        UniqueConstraint("loan_file_id", "check_type", name="uq_review_tasks_file_check"),
        Index("ix_review_tasks_maker_id_status", "maker_id", "status"),
        Index("ix_review_tasks_checker_id_status", "checker_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_file_id: Mapped[int] = mapped_column(
        ForeignKey("loan_files.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[CheckType] = mapped_column(Enum(CheckType, name="check_type"))
    status: Mapped[ReviewTaskStatus] = mapped_column(
        Enum(ReviewTaskStatus, name="review_task_status"),
        default=ReviewTaskStatus.PENDING_MAKER,
        server_default=ReviewTaskStatus.PENDING_MAKER.value,
    )
    maker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    checker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))

    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    checker_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    loan_file: Mapped["LoanFile"] = relationship(back_populates="review_tasks")
