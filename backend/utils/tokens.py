import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from core.settings import Settings
from models.users import User


class TokenError(Exception):
    """Base class for access-token validation failures."""


class TokenExpiredError(TokenError):
    pass


class TokenInvalidError(TokenError):
    pass


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _build_dummy_hash() -> str:
    return PasswordHash.recommended().hash("timing-equalizer-dummy-password")


_DUMMY_PASSWORD_HASH: str | None = None


def dummy_verify(password: str) -> None:
    """Burn comparable CPU time when the email is unknown (timing parity)."""
    global _DUMMY_PASSWORD_HASH
    from utils.authentication import verify_password

    if _DUMMY_PASSWORD_HASH is None:
        _DUMMY_PASSWORD_HASH = _build_dummy_hash()
    verify_password(password, _DUMMY_PASSWORD_HASH)


def create_access_token(user: User, session_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "sid": str(session_id),
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("access token expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalidError(str(exc)) from exc
