"""Login endpoint tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, select

from database import Base
from dependencies import get_db
from main import app
from models.refresh_sessions import RefreshSession
from models.users import User
from utils import rate_limit
from utils.authentication import hash_password

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine, class_=Session, autocommit=False, autoflush=False
)


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    rate_limit.reset()
    yield
    rate_limit.reset()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv(
        "JWT_SECRET", "test-secret-which-is-long-enough-for-hmac-sha256-signing"
    )
    from core.settings import get_settings

    get_settings.cache_clear()
    Base.metadata.create_all(bind=engine)

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


def _register(client: TestClient, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": email, "password": password},
    )


def _verify_user(email: str) -> None:
    with TestingSessionLocal() as db:
        user = db.exec(select(User).where(User.email == email)).one()
        user.is_verified = True
        db.add(user)
        db.commit()


def _make_user(email: str, *, verified: bool = True, active: bool = True) -> User:
    with TestingSessionLocal() as db:
        user = User(
            name="Direct User",
            email=email,
            password_hash=hash_password("password123"),
            is_verified=verified,
            is_active=active,
            verification_token="tok" if not verified else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _login(client: TestClient, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def test_login_success_sets_httponly_cookies_and_returns_user(client: TestClient):
    _register(client, "ok@example.com")
    _verify_user("ok@example.com")

    res = _login(client, "  OK@Example.COM  ".strip().lower())
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == "ok@example.com"
    assert body["user"]["name"] == "Test User"
    # Tokens never appear in the JSON body — only HttpOnly Set-Cookie headers.
    assert "access_token" not in res.text
    assert "refresh_token" not in res.text
    assert set(body.keys()) == {"user"}
    assert set(body["user"].keys()) == {"id", "email", "name"}

    set_cookie = res.headers.get_list("set-cookie")
    access = next(c for c in set_cookie if c.startswith("access_token="))
    refresh = next(c for c in set_cookie if c.startswith("refresh_token="))
    assert "HttpOnly" in access
    assert "HttpOnly" in refresh
    assert "Path=/" in access
    assert "Path=/api/v1/auth" in refresh


def test_unknown_email_and_wrong_password_same_error(client: TestClient):
    _make_user("known@example.com")

    unknown = _login(client, "unknown@example.com", "password123")
    wrong = _login(client, "known@example.com", "wrong-password")

    assert unknown.status_code == 401
    assert wrong.status_code == 401
    assert unknown.json()["detail"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["detail"]["code"] == "INVALID_CREDENTIALS"
    assert unknown.json()["detail"]["message"] == wrong.json()["detail"]["message"]
    # Wrong password never creates a session
    with TestingSessionLocal() as db:
        assert db.exec(select(RefreshSession)).all() == []


def test_unverified_email_rejected(client: TestClient):
    _register(client, "unverified@example.com")
    res = _login(client, "unverified@example.com")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "EMAIL_NOT_VERIFIED"


def test_disabled_account_rejected(client: TestClient):
    _make_user("disabled@example.com", active=False)
    res = _login(client, "disabled@example.com")
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ACCOUNT_UNAVAILABLE"


def test_missing_and_malformed_input_rejected(client: TestClient):
    missing = client.post("/api/v1/auth/login", json={"email": "a@b.com"})
    assert missing.status_code == 422
    assert missing.json()["detail"]["code"] == "VALIDATION_ERROR"

    bad_email = client.post(
        "/api/v1/auth/login", json={"email": "not-an-email", "password": "password123"}
    )
    assert bad_email.status_code == 422
    assert bad_email.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_login_normalizes_email_like_registration(client: TestClient):
    _register(client, "mixed@example.com")
    _verify_user("mixed@example.com")
    res = _login(client, "  Mixed@Example.com ")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "mixed@example.com"


def test_rate_limit_after_repeated_failures(client: TestClient):
    _make_user("brute@example.com")
    for _ in range(5):
        res = _login(client, "brute@example.com", "wrong")
        assert res.status_code == 401
    res = _login(client, "brute@example.com", "wrong")
    assert res.status_code == 429
    assert res.json()["detail"]["code"] == "RATE_LIMITED"


def test_login_creates_refresh_session_row(client: TestClient):
    _make_user("session@example.com")
    res = _login(client, "session@example.com")
    assert res.status_code == 200
    with TestingSessionLocal() as db:
        sessions = db.exec(select(RefreshSession)).all()
        assert len(sessions) == 1
        assert sessions[0].revoked_at is None
        assert len(sessions[0].token_hash) == 64


def test_register_stores_name(client: TestClient):
    res = _register(client, "named@example.com")
    assert res.status_code == 201
    assert res.json()["name"] == "Test User"
