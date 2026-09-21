import pytest
from core.settings import Settings
from database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine, class_=Session, autocommit=False, autoflush=False
    )
    yield factory
    engine.dispose()


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        email_max_attempts=5,
        email_retry_base_delay=1,
        email_max_retry_delay=10,
        email_max_concurrency=4,
        email_batch_size=100,
        email_poll_interval=0.01,
    )
