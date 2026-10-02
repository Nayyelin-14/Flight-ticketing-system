import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from core.settings import get_settings
from database import SessionLocal
from models.users import User
from utils.tokens import TokenError, decode_access_token


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_access_token(request: Request) -> str | None:
    """Prefer the HttpOnly access cookie; fall back to Authorization for other clients."""
    settings = get_settings()
    cookie_token = request.cookies.get(settings.access_cookie_name)
    if cookie_token:
        return cookie_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return None


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    settings = get_settings()
    token = get_access_token(request)
    if not token:
        raise _unauthorized("UNAUTHORIZED", "Authentication required")
    try:
        payload = decode_access_token(token, settings)
    except TokenError:
        raise _unauthorized("UNAUTHORIZED", "Authentication required") from None
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise _unauthorized("UNAUTHORIZED", "Authentication required") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("UNAUTHORIZED", "Authentication required")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
