import os
import threading
from datetime import UTC, datetime, timedelta

import pytest
from crud import outbox as outbox_crud
from database import Base
from models.outbox import JobStatus, JobType, OutboxJob
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, update


def _seed_job(
    session_factory,
    *,
    job_type=JobType.WELCOME_EMAIL.value,
    payload=None,
    status=JobStatus.PENDING,
    attempts=0,
    updated_at=None,
):
    with session_factory() as db:
        job = outbox_crud.create_outbox_job(db, job_type, payload or {})
        job.status = status.value
        job.attempts = attempts
        job.next_attempt_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
        job_id = job.id
    with session_factory() as db:
        if updated_at is not None:
            db.exec(
                update(OutboxJob)
                .where(OutboxJob.id == job_id)
                .values(updated_at=updated_at)
            )
            db.commit()
        return db.get(OutboxJob, job_id)


def _get_job(session_factory, job_id) -> OutboxJob | None:
    with session_factory() as db:
        return db.get(OutboxJob, job_id)


def test_create_outbox_job(session_factory):
    job = _seed_job(session_factory, payload={"recipient": "a@b.com"})
    stored = _get_job(session_factory, job.id)
    assert stored is not None
    assert stored.job_type == JobType.WELCOME_EMAIL
    assert stored.payload == {"recipient": "a@b.com"}
    assert stored.status == JobStatus.PENDING
    assert stored.attempts == 0
    assert stored.next_attempt_at is not None


def test_claim_eligible_jobs_marks_processing_and_returns_rows(session_factory):
    job = _seed_job(session_factory)
    jobs = outbox_crud.claim_eligible_jobs(session_factory, batch_size=100)
    assert [j.id for j in jobs] == [job.id]
    stored = _get_job(session_factory, job.id)
    assert stored.status == JobStatus.PROCESSING


def test_claim_ignores_future_and_non_pending_jobs(session_factory):
    _seed_job(session_factory, status=JobStatus.COMPLETED)
    _seed_job(session_factory, status=JobStatus.PROCESSING)
    _seed_job(session_factory, status=JobStatus.FAILED)
    future_attempt = _seed_job(session_factory)
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == future_attempt.id)
            .values(next_attempt_at=datetime.now(UTC) + timedelta(hours=1))
        )
        db.commit()
    assert outbox_crud.claim_eligible_jobs(session_factory) == []


def test_claim_returns_none_when_nothing_eligible(session_factory):
    assert outbox_crud.claim_eligible_jobs(session_factory) == []


def test_claim_respects_batch_size(session_factory):
    for _ in range(3):
        _seed_job(session_factory)
    jobs = outbox_crud.claim_eligible_jobs(session_factory, batch_size=2)
    assert len(jobs) == 2


def test_claim_is_exclusive_between_batches(session_factory):
    for _ in range(2):
        _seed_job(session_factory)
    first = outbox_crud.claim_eligible_jobs(session_factory)
    second = outbox_crud.claim_eligible_jobs(session_factory)
    assert first and second == []


def test_mark_completed(session_factory):
    job = _seed_job(session_factory)
    outbox_crud.mark_completed(session_factory, job_id=job.id)
    stored = _get_job(session_factory, job.id)
    assert stored.status == JobStatus.COMPLETED
    assert stored.completed_at is not None


def test_mark_failed(session_factory):
    job = _seed_job(session_factory)
    outbox_crud.mark_failed(session_factory, job_id=job.id, error="boom")
    stored = _get_job(session_factory, job.id)
    assert stored.status == JobStatus.FAILED
    assert stored.last_error == "boom"
    assert stored.completed_at is not None


def test_schedule_retry(session_factory):
    job = _seed_job(session_factory, attempts=1)
    outbox_crud.schedule_retry(session_factory, job=job, delay_seconds=60, error="temp")
    stored = _get_job(session_factory, job.id)
    assert stored.status == JobStatus.PENDING
    assert stored.attempts == 2
    assert stored.last_error == "temp"
    assert stored.next_attempt_at is not None
    assert stored.next_attempt_at > datetime.now(UTC).replace(tzinfo=None)


def test_recover_stale_jobs(session_factory):
    job = _seed_job(
        session_factory,
        status=JobStatus.PROCESSING,
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    recovered = outbox_crud.recover_stale_jobs(
        session_factory, processing_timeout_seconds=60
    )
    assert recovered == [job.id]
    assert _get_job(session_factory, job.id).status == JobStatus.PENDING


def test_recover_ignores_recent_processing(session_factory):
    _seed_job(
        session_factory,
        status=JobStatus.PROCESSING,
        updated_at=datetime.now(UTC),
    )
    recovered = outbox_crud.recover_stale_jobs(
        session_factory, processing_timeout_seconds=60
    )
    assert recovered == []


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="requires TEST_POSTGRES_URL env var",
)
def test_claim_concurrent_postgres_does_not_double_claim():
    """Two workers claiming the store at once must not claim the same job twice."""
    from sqlalchemy.pool import NullPool

    url = os.environ["TEST_POSTGRES_URL"]
    engine = create_engine(url, poolclass=NullPool, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        bind=engine, class_=Session, autocommit=False, autoflush=False
    )
    try:
        jobs = [_seed_job(factory) for _ in range(5)]
        results: list[int] = []
        barrier = threading.Barrier(2)

        def claim() -> None:
            barrier.wait()
            results.append(
                len(outbox_crud.claim_eligible_jobs(factory, batch_size=100))
            )

        threads = [threading.Thread(target=claim) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == len(jobs)
    finally:
        engine.dispose()
