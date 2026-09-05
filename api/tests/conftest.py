import os
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from types import TracebackType
from typing import Any

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.deps import require_roles
from app.main import app
from app.models import Base
from app.models.loan_document import LoanDocument
from app.models.loan_file import LoanFile, LoanFileStatus, ProductType
from app.models.review_task import CHECK_TYPE_ORDER, ReviewTask, ReviewTaskStatus
from app.models.user import Role, Team, User
from app.security import create_access_token, hash_password

# Prefer a real Postgres in CI; fall back to in-memory SQLite locally.
TEST_DB_URL = (
    os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "sqlite+pysqlite:///:memory:"
)

if TEST_DB_URL.startswith("sqlite"):
    engine = create_engine(
        TEST_DB_URL,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(TEST_DB_URL, future=True)

TestingSessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


# --- Probe routes -----------------------------------------------------------
# The roadmap's RBAC tests need a "protected probe route" per role. Kept here so
# production never mounts it.

_PROBE_ROLES = {
    "ops-maker": Role.OPS_MAKER,
    "ops-checker": Role.OPS_CHECKER,
    "uw-maker": Role.UW_MAKER,
    "uw-checker": Role.UW_CHECKER,
    "admin": Role.ADMIN,
}


def _probe_endpoint(role: Role) -> Callable[..., dict[str, str]]:
    def _endpoint(user: User = Depends(require_roles(role))) -> dict[str, str]:
        return {"role": user.role.value}

    return _endpoint


_probe_router = APIRouter(prefix="/_probe", tags=["probe"])
for _slug, _role in _PROBE_ROLES.items():
    _probe_router.add_api_route(f"/{_slug}", _probe_endpoint(_role), methods=["GET"])

if not any(r.path.startswith("/_probe") for r in app.routes):  # type: ignore[attr-defined]
    app.include_router(_probe_router)


# --- Schema / session fixtures --------------------------------------------


@pytest.fixture(autouse=True)
def _schema() -> Iterator[None]:
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Iterator[Session]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    def _get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- User / auth fixtures -------------------------------------------------

_TEAM_FOR_ROLE = {
    Role.OPS_MAKER: Team.OPS,
    Role.OPS_CHECKER: Team.OPS,
    Role.UW_MAKER: Team.UW,
    Role.UW_CHECKER: Team.UW,
    Role.ADMIN: None,
}


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    counter = {"n": 0}

    def _make(
        role: Role = Role.OPS_MAKER,
        *,
        password: str = "pw",
        email: str | None = None,
        is_active: bool = True,
    ) -> User:
        counter["n"] += 1
        user = User(
            email=email or f"{role.value.lower()}-{counter['n']}@loanflow.dev",
            full_name=f"{role.value.title()} {counter['n']}",
            password_hash=hash_password(password),
            role=role,
            team=_TEAM_FOR_ROLE[role],
            is_active=is_active,
        )
        db.add(user)
        db.flush()
        return user

    return _make


@pytest.fixture
def token_headers() -> Callable[[User], dict[str, str]]:
    def _headers(user: User) -> dict[str, str]:
        token = create_access_token(user.id, user.role.value)
        return {"Authorization": f"Bearer {token}"}

    return _headers


@pytest.fixture
def ops_maker(make_user: Callable[..., User]) -> User:
    return make_user(Role.OPS_MAKER)


@pytest.fixture
def ops_checker(make_user: Callable[..., User]) -> User:
    return make_user(Role.OPS_CHECKER)


@pytest.fixture
def uw_maker(make_user: Callable[..., User]) -> User:
    return make_user(Role.UW_MAKER)


@pytest.fixture
def uw_checker(make_user: Callable[..., User]) -> User:
    return make_user(Role.UW_CHECKER)


@pytest.fixture
def admin(make_user: Callable[..., User]) -> User:
    return make_user(Role.ADMIN)


@pytest.fixture
def auth_ops_maker(
    ops_maker: User, token_headers: Callable[[User], dict[str, str]]
) -> dict[str, str]:
    return token_headers(ops_maker)


@pytest.fixture
def auth_ops_checker(
    ops_checker: User, token_headers: Callable[[User], dict[str, str]]
) -> dict[str, str]:
    return token_headers(ops_checker)


@pytest.fixture
def auth_uw_maker(
    uw_maker: User, token_headers: Callable[[User], dict[str, str]]
) -> dict[str, str]:
    return token_headers(uw_maker)


@pytest.fixture
def auth_uw_checker(
    uw_checker: User, token_headers: Callable[[User], dict[str, str]]
) -> dict[str, str]:
    return token_headers(uw_checker)


@pytest.fixture
def auth_admin(admin: User, token_headers: Callable[[User], dict[str, str]]) -> dict[str, str]:
    return token_headers(admin)


# --- Loan-file / task fixtures ------------------------------------------------


@pytest.fixture(autouse=True)
def _upload_dir(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never touch the real upload directory during tests."""
    monkeypatch.setattr("app.config.settings.upload_dir", str(tmp_path / "uploads"))


@pytest.fixture
def uw_makers(make_user: Callable[..., User]) -> list[User]:
    return [make_user(Role.UW_MAKER) for _ in range(3)]


@pytest.fixture
def uw_checkers(make_user: Callable[..., User]) -> list[User]:
    return [make_user(Role.UW_CHECKER) for _ in range(2)]


@pytest.fixture
def make_loan_file(db: Session, make_user: Callable[..., User]) -> Callable[..., LoanFile]:
    counter = {"n": 0}

    def _make(
        *,
        created_by: User | None = None,
        status: LoanFileStatus = LoanFileStatus.DRAFT,
        documents: int = 0,
        loan_amount: Decimal = Decimal("25000.00"),
        product_type: ProductType = ProductType.TERM_LOAN,
    ) -> LoanFile:
        counter["n"] += 1
        n = counter["n"]
        owner = created_by or make_user(Role.OPS_MAKER)
        loan_file = LoanFile(
            status=status,
            product_type=product_type,
            loan_amount=loan_amount,
            currency="USD",
            applicant_full_name=f"Applicant {n}",
            applicant_email=f"applicant-{n}@example.com",
            applicant_dob=date(1990, 1, 1),
            created_by_id=owner.id,
        )
        db.add(loan_file)
        db.flush()
        for i in range(documents):
            db.add(
                LoanDocument(
                    loan_file_id=loan_file.id,
                    filename=f"doc-{n}-{i}.pdf",
                    content_type="application/pdf",
                    byte_size=10,
                    sha256=f"{n:032x}{i:032x}"[:64],
                    storage_path=f"{loan_file.id}/doc-{i}.pdf",
                    uploaded_by_id=owner.id,
                )
            )
        db.flush()
        return loan_file

    return _make


@pytest.fixture
def assign_tasks(db: Session) -> Callable[..., list[ReviewTask]]:
    """Insert the four review tasks for a file without going through submit()."""

    def _assign(loan_file: LoanFile, makers: list[User], checkers: list[User]) -> list[ReviewTask]:
        tasks = []
        for i, check_type in enumerate(CHECK_TYPE_ORDER):
            task = ReviewTask(
                loan_file_id=loan_file.id,
                check_type=check_type,
                status=ReviewTaskStatus.PENDING_MAKER,
                maker_id=makers[i % len(makers)].id,
                checker_id=checkers[i % len(checkers)].id,
                version=1,
            )
            db.add(task)
            tasks.append(task)
        db.flush()
        return tasks

    return _assign


class QueryCounter:
    """Count SQL statements executed on `engine` within a `with` block."""

    def __init__(self, target_engine: Any) -> None:
        self.engine = target_engine
        self.statements: list[str] = []

    def _record(
        self,
        _conn: Connection,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        self.statements.append(statement)

    def __enter__(self) -> "QueryCounter":
        event.listen(self.engine, "before_cursor_execute", self._record)
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        event.remove(self.engine, "before_cursor_execute", self._record)
