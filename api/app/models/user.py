import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import expression

from . import Base, TimestampMixin


class Role(str, enum.Enum):
    OPS_MAKER = "OPS_MAKER"
    OPS_CHECKER = "OPS_CHECKER"
    UW_MAKER = "UW_MAKER"
    UW_CHECKER = "UW_CHECKER"
    ADMIN = "ADMIN"


class Team(str, enum.Enum):
    OPS = "OPS"
    UW = "UW"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"))
    team: Mapped[Team | None] = mapped_column(Enum(Team, name="team"), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        default=True, server_default=expression.true(), nullable=False
    )
