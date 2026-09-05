from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base

if TYPE_CHECKING:
    from .loan_file import LoanFile


class TaskEvent(Base):
    """Append-only audit row. One per state transition (plus a few non-transition
    events like document uploads). `action` values are the `ACTION_*` constants in
    `api/app/services/state_machine.py`.
    """

    __tablename__ = "task_events"
    __table_args__ = (
        Index("ix_task_events_loan_file_id_created_at", "loan_file_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    loan_file_id: Mapped[int] = mapped_column(ForeignKey("loan_files.id", ondelete="CASCADE"))
    review_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("review_tasks.id", ondelete="CASCADE"), nullable=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    loan_file: Mapped["LoanFile"] = relationship(back_populates="events")
