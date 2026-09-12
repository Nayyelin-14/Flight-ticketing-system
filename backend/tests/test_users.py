import uuid

import pytest
from database import Base
from dependencies import get_db
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=engine, class_=Session, autocommit=False, autoflush=False
)


@pytest.fixture()
def client():
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


def test_register_returns_201_with_user(client: TestClient):
    res = client.post(
        "/users/register/",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "user@example.com"
    assert "created_at" in body
    uuid.UUID(body["id"])
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client: TestClient):
    payload = {"email": "dup@example.com", "password": "password123"}
    first = client.post("/users/register/", json=payload)
    assert first.status_code == 201

    second = client.post("/users/register/", json=payload)
    assert second.status_code == 409


def test_register_normalizes_email_to_lowercase(client: TestClient):
    res = client.post(
        "/users/register/",
        json={"email": "MixedCase@Example.com", "password": "password123"},
    )
    assert res.status_code == 201
    assert res.json()["email"] == "mixedcase@example.com"


def test_register_rejects_short_password(client: TestClient):
    res = client.post(
        "/users/register/",
        json={"email": "short@example.com", "password": "123"},
    )
    assert res.status_code == 422


def test_register_rejects_invalid_email(client: TestClient):
    res = client.post(
        "/users/register/",
        json={"email": "not-an-email", "password": "password123"},
    )
    assert res.status_code == 422
