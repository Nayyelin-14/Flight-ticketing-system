from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from core.settings import Settings, get_settings
from crud import refresh_sessions as session_crud
from crud.users import create_user, get_user_by_email
from dependencies import CurrentUser, DbSession
from models.users import User
from schemas.auth import AuthUserResponse, LoginRequest, LoginResponse, MeResponse
from schemas.users import UserCreate, UserResponse
from utils.authentication import verify_password
from utils.cookies import clear_auth_cookies, set_auth_cookies
from utils.rate_limit import RateLimitedError, check_rate_limit
from utils.tokens import create_access_token, dummy_verify

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


def _err(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _user_summary(user: User) -> AuthUserResponse:
    return AuthUserResponse(id=str(user.id), email=user.email, name=user.name)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(body: UserCreate, db: DbSession) -> User:
    if get_user_by_email(db, body.email) is not None:
        raise _err(
            status.HTTP_409_CONFLICT,
            "EMAIL_ALREADY_REGISTERED",
            "Email is already registered",
        )

    try:
        return create_user(db, body)
    except IntegrityError:
        db.rollback()
        raise _err(
            status.HTTP_409_CONFLICT,
            "EMAIL_ALREADY_REGISTERED",
            "Email is already registered",
        ) from None


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
) -> LoginResponse:
    ip = _client_ip(request)
    try:
        check_rate_limit(
            [f"login:email:{body.email}", f"login:ip:{ip}"],
            max_attempts=settings.login_rate_max_attempts,
            window_seconds=settings.login_rate_window_seconds,
        )
    except RateLimitedError:
        raise _err(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Too many login attempts. Please try again later.",
        ) from None

    user = get_user_by_email(db, body.email)
    if user is None:
        dummy_verify(body.password)
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
        )

    if not verify_password(body.password, user.password_hash):
        raise _err(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
        )

    if not user.is_verified:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "EMAIL_NOT_VERIFIED",
            "Please verify your email before logging in.",
        )

    if not user.is_active:
        raise _err(
            status.HTTP_403_FORBIDDEN,
            "ACCOUNT_UNAVAILABLE",
            "This account is currently unavailable.",
        )

    session_crud.purge_expired(db)
    raw_refresh, session = session_crud.start_session(
        db,
        user,
        ttl_seconds=settings.refresh_token_ttl,
        user_agent=request.headers.get("user-agent"),
        ip_address=ip,
    )
    access = create_access_token(user, session.id, settings)
    db.commit()
    set_auth_cookies(
        response, access_token=access, refresh_token=raw_refresh, settings=settings
    )
    return LoginResponse(user=_user_summary(user))


def _refresh_rejected(settings: Settings, response: Response) -> JSONResponse:
    """401 + clear both auth cookies (cookies must live on the returned response)."""
    clear_auth_cookies(response, settings)
    out = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": {
                "code": "REFRESH_TOKEN_INVALID",
                "message": "Invalid or expired session.",
            }
        },
    )
    for name, value in response.headers.items():
        if name.lower() == "set-cookie":
            out.headers.append("set-cookie", value)
    # delete_cookie encodes as Set-Cookie with empty value + Max-Age=0
    for cookie in response.raw_headers:
        if cookie[0].lower() == b"set-cookie":
            out.raw_headers.append(cookie)
    return out


@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=None)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
) -> dict | JSONResponse:
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        return _refresh_rejected(settings, response)

    presented = session_crud.get_session_by_raw_token(db, raw)
    if presented is None:
        return _refresh_rejected(settings, response)

    locked = session_crud.lock_session(db, presented)
    if locked is None:
        return _refresh_rejected(settings, response)

    now = datetime.now(UTC)
    if locked.revoked_at is not None:
        if locked.replaced_by is not None:
            session_crud.revoke_family(db, locked.family_id)
            db.commit()
        return _refresh_rejected(settings, response)

    if _as_utc(locked.expires_at) <= now:
        session_crud.revoke_session(db, locked)
        db.commit()
        return _refresh_rejected(settings, response)

    user = db.get(User, locked.user_id)
    if user is None or not user.is_active:
        session_crud.revoke_family(db, locked.family_id)
        db.commit()
        return _refresh_rejected(settings, response)

    new_raw, new_session = session_crud.rotate_session(
        db,
        locked,
        user_agent=request.headers.get("user-agent"),
        ip_address=_client_ip(request),
    )
    access = create_access_token(user, new_session.id, settings)
    db.commit()
    set_auth_cookies(
        response, access_token=access, refresh_token=new_raw, settings=settings
    )
    return {"user": _user_summary(user)}


@router.get("/me", response_model=MeResponse, status_code=status.HTTP_200_OK)
def me(current_user: CurrentUser) -> MeResponse:
    return MeResponse(user=_user_summary(current_user))


class VerifyEmailRequest(BaseModel):
    token: str


@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(body: VerifyEmailRequest, db: DbSession) -> dict:
    from crud.users import get_user_by_verification_token

    user = get_user_by_verification_token(db, body.token)
    if user is None:
        raise _err(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_TOKEN",
            "Invalid or already used verification token",
        )

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    db.add(user)
    db.commit()
    return {"message": "Email verified successfully"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: SettingsDep,
) -> Response:
    raw = request.cookies.get(settings.refresh_cookie_name)
    if raw:
        session = session_crud.get_session_by_raw_token(db, raw)
        if session is not None:
            session_crud.revoke_family(db, session.family_id)
            db.commit()
    clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
