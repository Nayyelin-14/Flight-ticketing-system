from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.settings import get_settings
from database import engine
from routers import auth
from utils.security import install_security

app = FastAPI()

_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
install_security(app, _settings)


API_V1 = _settings.api_v1_prefix

app.include_router(auth.router, prefix=API_V1)


@app.get("/")
def hello():
    return {"message": "Flight Booking API"}


@app.get("/health/db")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {"database": "connected"}

    except SQLAlchemyError as e:
        return {"database": "disconnected", "error": str(e)}
