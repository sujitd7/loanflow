import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .loan_file import LoanFile


class DocumentKind(str, enum.Enum):
    IDENTITY = "IDENTITY"
    INCOME_PROOF = "INCOME_PROOF"
    BANK_STATEMENT = "BANK_STATEMENT"
    TAX_RETURN = "TAX_RETURN"
    COLLATERAL = "COLLATERAL"
    OTHER = "OTHER"


class LoanDocument(Base):
    """An uploaded file attached to a loan file. Immutable once written."""

    __tablename__ = "loan_documents"
    __table_args__ = (
        UniqueConstraint("loan_file_id", "sha256", name="uq_loan_documents_file_sha"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_file_id: Mapped[int] = mapped_column(
        ForeignKey("loan_files.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(String(500))
    kind: Mapped[DocumentKind | None] = mapped_column(
        Enum(DocumentKind, name="document_kind"), nullable=True
    )
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    loan_file: Mapped["LoanFile"] = relationship(back_populates="documents")
