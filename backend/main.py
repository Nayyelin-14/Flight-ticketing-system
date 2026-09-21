from database import engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import auth, users
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


API_V1 = "/api/v1"

app.include_router(users.router, prefix=API_V1)
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
