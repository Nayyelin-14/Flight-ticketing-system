from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.settings import Settings

_STATE_CHANGING_AUTH_PATHS = frozenset(
    {
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    }
)


def install_security(app: FastAPI, settings: Settings) -> None:
    allowed = set(settings.cors_origins)

    class OriginCheckMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if (
                request.method in ("POST", "PUT", "PATCH", "DELETE")
                and request.url.path in _STATE_CHANGING_AUTH_PATHS
            ):
                origin = request.headers.get("origin")
                if origin is not None and origin not in allowed:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": {
                                "code": "ORIGIN_NOT_ALLOWED",
                                "message": "Request origin is not allowed.",
                            }
                        },
                    )
            return await call_next(request)

    app.add_middleware(OriginCheckMiddleware)

    # ဒီ decorator က RequestValidationError ဖြစ်တဲ့အခါ ဒီ function ကို ခေါ်ဖို့ FastAPI ကို ပြောတာပါ။
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "VALIDATION_ERROR",
                    "message": "Please enter a valid email and password.",
                }
            },
        )
