"""Auth / RBAC dependencies.

`get_current_user` resolves the bearer access token to a `User`; `require_roles`
builds a dependency that additionally checks the user's role. Routes declare RBAC
with `user = Depends(require_roles(Role.X, ...))`, never in handler bodies.
"""

from collections.abc import Callable

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .errors import Forbidden, Unauthorized
from .models.user import Role, User
from .security import decode_token

__all__ = ["Role", "get_current_user", "require_roles"]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise Unauthorized("Not authenticated")
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise Unauthorized("Invalid token") from exc

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Unauthorized("Invalid token") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Unknown or inactive user")
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise Forbidden("Insufficient permissions")
        return user

    return _dep
