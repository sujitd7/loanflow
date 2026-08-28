from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models.user import User
from ..schemas.auth import LoginIn, LogoutIn, RefreshIn, TokenPair, UserOut
from ..services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenPair:
    user = auth_service.authenticate(db, body.email, body.password)
    return auth_service.issue_pair(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)) -> TokenPair:
    return auth_service.rotate(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    body: LogoutIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    auth_service.revoke(db, body.refresh_token, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
