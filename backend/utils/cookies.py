"""Cookie helpers for HttpOnly auth cookies.

The browser is the sole credential store: both tokens live in HttpOnly cookies.
The Authorization-header path remains available for non-browser clients via
``get_current_user``, but the Next.js app never sees raw tokens.
"""

from fastapi import Response

from core.settings import Settings


def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    settings: Settings,
) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
    }
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        max_age=settings.access_token_ttl,
        path="/",
        **common,
    )
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=min(settings.refresh_token_ttl, 604800),
        path=settings.refresh_cookie_path,
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.access_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
