import uuid

import pytest
from database import Base
from dependencies import get_db
from fastapi.testclient import TestClient
from main import app
from models.outbox import JobStatus, JobType, OutboxJob
from models.users import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, select

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

    with TestingSessionLocal() as db:
        jobs = db.exec(select(OutboxJob)).all()
        assert len(jobs) == 1


def test_register_creates_pending_welcome_outbox_job(client: TestClient):
    res = client.post(
        "/users/register/",
        json={"email": "job@example.com", "password": "password123"},
    )
    assert res.status_code == 201

    with TestingSessionLocal() as db:
        job = db.exec(select(OutboxJob)).one()
    assert job.job_type == JobType.WELCOME_EMAIL
    assert job.status == JobStatus.PENDING
    assert job.attempts == 0
    assert job.payload["recipient"] == "job@example.com"
    assert uuid.UUID(job.payload["user_id"])


def test_register_rolls_back_user_when_outbox_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    import crud.outbox as outbox_module

    def boom(db, job_type, payload):
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(outbox_module, "create_outbox_job", boom)

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.post(
            "/users/register/",
            json={"email": "rollback@example.com", "password": "password123"},
        )
    assert res.status_code == 500

    with TestingSessionLocal() as db:
        assert (
            db.exec(select(User).where(User.email == "rollback@example.com")).first()
            is None
        )
        assert db.exec(select(OutboxJob)).all() == []


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
