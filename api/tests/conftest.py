import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.deps import require_roles
from app.main import app
from app.models import Base
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
