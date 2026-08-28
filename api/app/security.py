"""Password hashing (Argon2) and JWT encode/decode.

Two token types share one secret but carry a `type` claim so an access token can
never be replayed as a refresh token and vice versa.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from .config import settings

_hasher = PasswordHasher()


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


# A valid Argon2 hash of a value nobody uses. Verify against this when the email
# is unknown so login timing does not reveal whether an account exists.
DUMMY_PASSWORD_HASH = _hasher.hash("no-such-user")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except Argon2Error:
        return False


def _encode(claims: dict[str, Any], ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {**claims, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    return _encode(
        {"sub": str(user_id), "type": "access", "role": role},
        timedelta(minutes=settings.jwt_access_ttl_minutes),
    )


def create_refresh_token(user_id: int, jti: str) -> str:
    return _encode(
        {"sub": str(user_id), "type": "refresh", "jti": jti},
        timedelta(days=settings.jwt_refresh_ttl_days),
    )


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and verify a token. Raises `jwt.PyJWTError` on any problem:
    bad signature, expiry, a missing required claim, or a `type` claim that
    does not match `expected_type`."""
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub", "type"]},
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload
