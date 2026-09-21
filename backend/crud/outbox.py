import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from database import SessionLocal
from models.outbox import JobStatus, OutboxJob
from sqlalchemy import update
from sqlmodel import Session, select

SessionFactory = Callable[[], Session]


def create_outbox_job(db: Session, job_type: str, payload: dict) -> OutboxJob:
    job = OutboxJob(
        job_type=job_type,
        payload=payload,
        status=JobStatus.PENDING.value,
        attempts=0,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(job)
    return job


def claim_eligible_jobs(
    session_factory: SessionFactory = SessionLocal,
    *,
    batch_size: int = 100,
) -> list[OutboxJob]:
    now = datetime.now(UTC)
    with session_factory() as db:
        ids_stmt = (
            select(OutboxJob.id)
            .where(
                OutboxJob.status == JobStatus.PENDING.value,
                OutboxJob.next_attempt_at <= now,
            )
            .order_by(OutboxJob.created_at.asc())
            .limit(batch_size)
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            ids_stmt = ids_stmt.with_for_update(skip_locked=True)

        ids = list(db.execute(ids_stmt).scalars())
        if not ids:
            return []

        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id.in_(ids))
            .values(status=JobStatus.PROCESSING.value, updated_at=now)
        )
        db.commit()

        jobs = db.exec(
            select(OutboxJob)
            .where(OutboxJob.id.in_(ids))
            .order_by(OutboxJob.created_at.asc())
        ).all()
        return list(jobs)


def recover_stale_jobs(
    session_factory: SessionFactory = SessionLocal,
    *,
    processing_timeout_seconds: int = 120,
) -> list[uuid.UUID]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=processing_timeout_seconds)
    with session_factory() as db:
        ids_stmt = select(OutboxJob.id).where(
            OutboxJob.status == JobStatus.PROCESSING.value,
            OutboxJob.updated_at <= cutoff,
        )
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            ids_stmt = ids_stmt.with_for_update(skip_locked=True)

        ids = list(db.execute(ids_stmt).scalars())
        if not ids:
            return ids

        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id.in_(ids))
            .values(status=JobStatus.PENDING.value, updated_at=now)
        )
        db.commit()
        return ids


def mark_completed(
    session_factory: SessionFactory = SessionLocal, *, job_id: uuid.UUID
) -> None:
    now = datetime.now(UTC)
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == job_id)
            .values(
                status=JobStatus.COMPLETED.value,
                completed_at=now,
                updated_at=now,
            )
        )
        db.commit()


def mark_failed(
    session_factory: SessionFactory = SessionLocal,
    *,
    job_id: uuid.UUID,
    error: str,
) -> None:
    now = datetime.now(UTC)
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == job_id)
            .values(
                status=JobStatus.FAILED.value,
                last_error=error[:1000],
                completed_at=now,
                updated_at=now,
            )
        )
        db.commit()


def schedule_retry(
    session_factory: SessionFactory = SessionLocal,
    *,
    job: OutboxJob,
    delay_seconds: int,
    error: str,
) -> None:
    now = datetime.now(UTC)
    next_attempt_at = now + timedelta(seconds=delay_seconds)
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == job.id)
            .values(
                status=JobStatus.PENDING.value,
                attempts=job.attempts + 1,
                last_error=error[:1000],
                next_attempt_at=next_attempt_at,
                updated_at=now,
            )
        )
        db.commit()
