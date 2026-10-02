"""Refresh, /me, logout, and access-token validation tests."""

from datetime import UTC, datetime, timedelta

import jwt
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
from utils.tokens import create_access_token

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


def _seed_verified_user(email: str = "user@example.com") -> User:
    with TestingSessionLocal() as db:
        user = User(
            name="Refresh User",
            email=email,
            password_hash=hash_password("password123"),
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user


def _login(client: TestClient, email: str = "user@example.com") -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert res.status_code == 200, res.text
    return dict(client.cookies)


def _cookie_value(client: TestClient, name: str) -> str | None:
    return client.cookies.get(name)


def test_me_with_valid_access_cookie(client: TestClient):
    _seed_verified_user()
    _login(client)
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "user@example.com"
    assert res.json()["user"]["name"] == "Refresh User"
    assert set(res.json().keys()) == {"user"}
    assert set(res.json()["user"].keys()) == {"id", "email", "name"}


def test_refresh_response_body_has_no_tokens(client: TestClient):
    _seed_verified_user()
    _login(client)
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    assert "access_token" not in res.text
    assert "refresh_token" not in res.text
    assert set(res.json().keys()) == {"user"}


def test_me_without_token_401(client: TestClient):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "UNAUTHORIZED"


def test_me_with_expired_access_token_401(client: TestClient):
    user = _seed_verified_user()
    with TestingSessionLocal() as db:
        session = RefreshSession(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    from core.settings import get_settings

    settings = get_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(session.id),
            "jti": "jti",
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=30),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_me_with_malformed_token_401(client: TestClient):
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert res.status_code == 401


def test_me_with_wrongly_signed_token_401(client: TestClient):
    user = _seed_verified_user()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(user.id),
            "sid": "x",
            "jti": "j",
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "iss": "skyflare",
            "aud": "skyflare-api",
        },
        "wrong-secret",
        algorithm="HS256",
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_me_for_deleted_user_401(client: TestClient):
    user = _seed_verified_user()
    with TestingSessionLocal() as db:
        session = RefreshSession(
            user_id=user.id,
            token_hash="b" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    from core.settings import get_settings

    token = create_access_token(user, session.id, get_settings())
    # Soft "delete": mark inactive (also covers disabled user case)
    with TestingSessionLocal() as db:
        u = db.get(User, user.id)
        u.is_active = False
        db.add(u)
        db.commit()
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


def test_refresh_rotates_token_and_issues_new_access(client: TestClient):
    _seed_verified_user()
    _login(client)
    old_refresh = _cookie_value(client, "refresh_token")
    old_access = _cookie_value(client, "access_token")
    assert old_refresh and old_access

    with TestingSessionLocal() as db:
        family = db.exec(select(RefreshSession)).one().family_id
        root_expires = db.exec(select(RefreshSession)).one().expires_at

    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    new_refresh = _cookie_value(client, "refresh_token")
    new_access = _cookie_value(client, "access_token")
    assert new_refresh != old_refresh
    assert new_access != old_access

    with TestingSessionLocal() as db:
        sessions = list(db.exec(select(RefreshSession)).all())
        assert len(sessions) == 2
        active = [s for s in sessions if s.revoked_at is None]
        revoked = [s for s in sessions if s.revoked_at is not None]
        assert len(active) == 1
        assert len(revoked) == 1
        assert revoked[0].replaced_by == active[0].id
        assert active[0].family_id == family
        # Absolute expiry preserved across rotation
        assert active[0].expires_at == root_expires


def test_refresh_absolute_expires_not_extended(client: TestClient):

    _seed_verified_user()
    _login(client)
    with TestingSessionLocal() as db:
        root = db.exec(select(RefreshSession)).one()
        root.expires_at = datetime.now(UTC) + timedelta(hours=1)
        db.add(root)
        db.commit()
        original_expiry = root.expires_at

    client.post("/api/v1/auth/refresh")
    with TestingSessionLocal() as db:
        active = db.exec(
            select(RefreshSession).where(RefreshSession.revoked_at.is_(None))
        ).one()
        got = active.expires_at
        if got.tzinfo is None:
            got = got.replace(tzinfo=UTC)
        expected = original_expiry
        if expected.tzinfo is None:
            expected = expected.replace(tzinfo=UTC)
        assert abs((got - expected).total_seconds()) < 2


def test_refresh_without_cookie_401_clears_cookies(client: TestClient):
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "REFRESH_TOKEN_INVALID"
    # Confirm settings: refresh cookie is scoped to the API auth prefix.
    from core.settings import get_settings

    assert get_settings().refresh_cookie_path == "/api/v1/auth"


def test_refresh_with_garbage_token_401_clears_cookies(client: TestClient):
    client.cookies.set("refresh_token", "garbage-token-value")
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "REFRESH_TOKEN_INVALID"
    # Cookies cleared on failure
    cleared = res.headers.get_list("set-cookie")
    assert any("refresh_token=" in c for c in cleared)


def test_refresh_expired_session_rejected(client: TestClient):
    _seed_verified_user()
    _login(client)
    with TestingSessionLocal() as db:
        session = db.exec(select(RefreshSession)).one()
        session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.add(session)
        db.commit()

    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "REFRESH_TOKEN_INVALID"


def test_refresh_revoked_session_rejected(client: TestClient):
    _seed_verified_user()
    _login(client)
    with TestingSessionLocal() as db:
        session = db.exec(select(RefreshSession)).one()
        session.revoked_at = datetime.now(UTC)
        db.add(session)
        db.commit()

    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 401


def test_refresh_reuse_of_rotated_token_revokes_family(client: TestClient):
    _seed_verified_user()
    _login(client)
    old_refresh = _cookie_value(client, "refresh_token")
    assert old_refresh

    # First refresh succeeds and rotates
    res = client.post("/api/v1/auth/refresh")
    assert res.status_code == 200
    active_refresh = _cookie_value(client, "refresh_token")

    # Replay the old (rotated) token
    client.cookies.set("refresh_token", old_refresh)
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401
    assert reuse.json()["detail"]["code"] == "REFRESH_TOKEN_INVALID"

    # Entire family revoked — active token no longer works either
    with TestingSessionLocal() as db:
        sessions = db.exec(select(RefreshSession)).all()
        assert all(s.revoked_at is not None for s in sessions)

    client.cookies.set("refresh_token", active_refresh)
    after = client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


def test_concurrent_refresh_only_one_wins(client: TestClient):
    _seed_verified_user()
    _login(client)
    raw = _cookie_value(client, "refresh_token")
    assert raw

    # Simulate two concurrent requests by racing the same token hash:
    # first succeeds, second sees revoked+replaced → family kill / 401.
    first = client.post("/api/v1/auth/refresh")
    assert first.status_code == 200

    client.cookies.set("refresh_token", raw)
    second = client.post("/api/v1/auth/refresh")
    assert second.status_code == 401


def test_logout_revokes_session_and_clears_cookies(client: TestClient):
    _seed_verified_user()
    _login(client)

    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204

    with TestingSessionLocal() as db:
        sessions = db.exec(select(RefreshSession)).all()
        assert all(s.revoked_at is not None for s in sessions)

    # Refresh after logout fails
    refresh = client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 401


def test_logout_idempotent(client: TestClient):
    _seed_verified_user()
    _login(client)
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_logout_get_405_does_not_revoke_or_clear_cookies(client: TestClient):
    _seed_verified_user()
    _login(client)
    refresh_before = _cookie_value(client, "refresh_token")
    access_before = _cookie_value(client, "access_token")
    assert refresh_before and access_before

    res = client.get("/api/v1/auth/logout")
    assert res.status_code == 405
    assert "allow" in res.headers
    assert "POST" in res.headers["allow"]

    # Session not revoked
    with TestingSessionLocal() as db:
        sessions = db.exec(select(RefreshSession)).all()
        assert len(sessions) == 1
        assert sessions[0].revoked_at is None

    # Cookies untouched (no Set-Cookie clearing headers)
    set_cookie = res.headers.get_list("set-cookie")
    assert set_cookie == []
    assert _cookie_value(client, "refresh_token") == refresh_before
    assert _cookie_value(client, "access_token") == access_before

    # Session still usable via refresh
    refresh = client.post("/api/v1/auth/refresh")
    assert refresh.status_code == 200


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE", "PATCH"])
def test_only_post_allowed_on_logout(client: TestClient, method: str):
    _seed_verified_user()
    _login(client)
    refresh_before = _cookie_value(client, "refresh_token")

    res = client.request(method, "/api/v1/auth/logout")
    assert res.status_code == 405

    with TestingSessionLocal() as db:
        sessions = db.exec(select(RefreshSession)).all()
        assert all(s.revoked_at is None for s in sessions)
    assert _cookie_value(client, "refresh_token") == refresh_before
    assert res.headers.get_list("set-cookie") == []


def test_origin_check_rejects_foreign_origin(client: TestClient):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "a@b.com", "password": "password123"},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_origin_check_allows_configured_origin(client: TestClient):
    _seed_verified_user()
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == 200


def test_authorization_header_fallback_for_non_browser_clients(client: TestClient):
    user = _seed_verified_user()
    with TestingSessionLocal() as db:
        session = RefreshSession(
            user_id=user.id,
            token_hash="c" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    from core.settings import get_settings

    token = create_access_token(user, session.id, get_settings())
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "user@example.com"
