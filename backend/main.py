from database import engine
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

app = FastAPI()


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
