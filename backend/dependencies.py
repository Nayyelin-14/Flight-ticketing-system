from collections.abc import Generator

from database import SessionLocal
from sqlmodel import Session


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
