from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Import new model modules here so Alembic autogenerate sees their tables,
    e.g. `from .user import User  # noqa: F401`.
    """


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


from .loan_document import DocumentKind, LoanDocument  # noqa: E402, F401
from .loan_file import LoanFile, LoanFileStatus, ProductType  # noqa: E402, F401
from .refresh_token import RefreshToken  # noqa: E402, F401
from .review_task import (  # noqa: E402, F401
    CHECK_TYPE_ORDER,
    CheckType,
    ReviewTask,
    ReviewTaskStatus,
)
from .task_event import TaskEvent  # noqa: E402, F401
from .user import Role, Team, User  # noqa: E402, F401
