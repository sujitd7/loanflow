"""Authentication business logic: credential check and refresh-token rotation.

Pure functions over a `Session`; they raise `app.errors.Unauthorized`, never
`HTTPException`. Callers (routers) rely on `get_db` to commit on success.
"""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..errors import Unauthorized
from ..models.refresh_token import RefreshToken
from ..models.user import User
from ..schemas.auth import TokenPair
from ..security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)

_BAD_CREDENTIALS = "Incorrect email or password"
_BAD_REFRESH = "Invalid or expired refresh token"


def _as_utc(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat those as UTC."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, DUMMY_PASSWORD_HASH)  # equalise timing
        raise Unauthorized(_BAD_CREDENTIALS)
    # Verify the hash regardless of is_active so a disabled account is not
    # distinguishable by response time.
    password_ok = verify_password(password, user.password_hash)
    if not password_ok or not user.is_active:
        raise Unauthorized(_BAD_CREDENTIALS)
    return user


def issue_pair(db: Session, user: User) -> TokenPair:
    jti = uuid.uuid4().hex
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days),
        )
    )
    db.flush()
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, jti),
    )


def rotate(db: Session, raw_refresh: str) -> TokenPair:
    try:
        payload = decode_token(raw_refresh, "refresh")
    except jwt.PyJWTError as exc:
        raise Unauthorized(_BAD_REFRESH) from exc

    now = datetime.now(UTC)
    # Lock the row for the duration of the transaction so two requests carrying
    # the same token cannot both rotate it (no-op on SQLite, which serialises
    # writes anyway).
    row = db.scalar(
        select(RefreshToken).where(RefreshToken.jti == payload.get("jti")).with_for_update()
    )
    if row is None:
        raise Unauthorized(_BAD_REFRESH)

    if row.revoked_at is not None:
        # The token was already rotated away — this is a replay. Burn the whole
        # family and commit it now: this side effect must survive the 401 that
        # follows (the request session is rolled back on the raised exception).
        _revoke_all_for_user(db, row.user_id, now)
        db.commit()
        raise Unauthorized(_BAD_REFRESH)

    if _as_utc(row.expires_at) < now:
        raise Unauthorized(_BAD_REFRESH)

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise Unauthorized(_BAD_REFRESH)

    row.revoked_at = now
    db.flush()
    return issue_pair(db, user)


def revoke(db: Session, raw_refresh: str, user_id: int) -> None:
    """Logout: revoke the presented token if it belongs to `user_id`.

    Never raises — an unknown, malformed, or foreign token is a silent no-op.
    """
    try:
        payload = decode_token(raw_refresh, "refresh")
    except jwt.PyJWTError:
        return
    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if row is not None and row.user_id == user_id and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.flush()


def _revoke_all_for_user(db: Session, user_id: int, when: datetime) -> None:
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    for row in rows:
        row.revoked_at = when
    db.flush()
