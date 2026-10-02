import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

from core.settings import Settings, get_settings
from database import Base
from utils import rate_limit


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch: pytest.MonkeyPatch):
    """Cookie Secure off so TestClient (http) round-trips cookies; fresh settings cache."""
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv(
        "JWT_SECRET", "test-secret-which-is-long-enough-for-hmac-sha256-signing"
    )
    monkeypatch.setenv("LOGIN_RATE_MAX_ATTEMPTS", "5")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def settings() -> Settings:
    return get_settings()


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
def client(session_factory, monkeypatch: pytest.MonkeyPatch):
    from dependencies import get_db
    from main import app

    def _override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    from fastapi.testclient import TestClient

    with TestClient(app, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()
