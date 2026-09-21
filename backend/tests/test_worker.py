import asyncio
import threading
from datetime import UTC, datetime, timedelta

from crud import outbox as outbox_crud
from jobs.base import JobPermanentError, JobRetryError
from jobs.registry import register_handler
from jobs.worker import process_jobs_once
from models.outbox import JobStatus, OutboxJob
from sqlmodel import update

COMPLETED_IDS: list[str] = []
PERMANENT_RAISED_IDS: list[str] = []
RETRY_ONCE_SEEN: set[str] = set()
ALWAYS_RETRY_RAISES_IDS: list[str] = []
GENERIC_EXC_IDS: list[str] = []
CONC_STATE = {"active": 0, "max_active": 0, "lock": threading.Lock()}


@register_handler("TEST_COMPLETE")
class CompleteHandler:
    async def handle(self, job: OutboxJob) -> None:
        COMPLETED_IDS.append(str(job.id))


@register_handler("TEST_PERMANENT")
class PermanentFailHandler:
    async def handle(self, job: OutboxJob) -> None:
        PERMANENT_RAISED_IDS.append(str(job.id))
        raise JobPermanentError("doomed")


@register_handler("TEST_RETRY_ONCE")
class RetryOnceHandler:
    async def handle(self, job: OutboxJob) -> None:
        if str(job.id) in RETRY_ONCE_SEEN:
            return
        RETRY_ONCE_SEEN.add(str(job.id))
        raise JobRetryError("transient outage")


@register_handler("TEST_ALWAYS_RETRY")
class AlwaysRetryHandler:
    async def handle(self, job: OutboxJob) -> None:
        ALWAYS_RETRY_RAISES_IDS.append(str(job.id))
        raise JobRetryError("keep trying")


@register_handler("TEST_GENERIC_EXC")
class GenericExcHandler:
    async def handle(self, job: OutboxJob) -> None:
        GENERIC_EXC_IDS.append(str(job.id))
        raise RuntimeError("unexpected bug")


@register_handler("TEST_SLOW")
class SlowHandler:
    async def handle(self, job: OutboxJob) -> None:
        with CONC_STATE["lock"]:
            CONC_STATE["active"] += 1
            CONC_STATE["max_active"] = max(
                CONC_STATE["max_active"], CONC_STATE["active"]
            )
        try:
            await asyncio.sleep(0.05)
        finally:
            with CONC_STATE["lock"]:
                CONC_STATE["active"] -= 1


def _run(coro) -> None:
    return asyncio.run(coro)


def _seed(session_factory, job_type: str, *, attempts: int = 0):
    with session_factory() as db:
        job = outbox_crud.create_outbox_job(db, job_type, {"key": "value"})
        job.attempts = attempts
        job.next_attempt_at = datetime.now(UTC) - timedelta(minutes=5)
        db.commit()
        return job.id


def _make_ready(session_factory, job_id) -> None:
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == job_id)
            .values(next_attempt_at=datetime.now(UTC) - timedelta(minutes=5))
        )
        db.commit()


def _get_job(session_factory, job_id) -> OutboxJob:
    with session_factory() as db:
        return db.get(OutboxJob, job_id)


def test_worker_completes_job(session_factory, settings):
    job_id = _seed(session_factory, "TEST_COMPLETE")
    processed = _run(process_jobs_once(settings, session_factory))
    assert processed == 1
    assert str(job_id) in COMPLETED_IDS
    assert _get_job(session_factory, job_id).status == JobStatus.COMPLETED


def test_worker_retries_transient_failure_then_succeeds(session_factory, settings):
    job_id = _seed(session_factory, "TEST_RETRY_ONCE", attempts=0)
    _run(process_jobs_once(settings, session_factory))

    after_first = _get_job(session_factory, job_id)
    assert after_first.status == JobStatus.PENDING
    assert after_first.attempts == 1
    assert "transient outage" in after_first.last_error
    assert after_first.next_attempt_at is not None
    assert after_first.next_attempt_at > datetime.now(UTC).replace(tzinfo=None)

    _make_ready(session_factory, job_id)
    _run(process_jobs_once(settings, session_factory))
    assert _get_job(session_factory, job_id).status == JobStatus.COMPLETED


def test_worker_fails_job_after_max_attempts(session_factory):
    from core.settings import Settings

    strict = Settings(
        email_max_attempts=3,
        email_retry_base_delay=1,
        email_max_retry_delay=10,
    )
    job_id = _seed(session_factory, "TEST_ALWAYS_RETRY", attempts=2)
    _run(process_jobs_once(strict, session_factory))
    after = _get_job(session_factory, job_id)
    assert after.status == JobStatus.FAILED
    assert after.attempts == 2
    assert "keep trying" in after.last_error


def test_worker_fails_permanent_error_immediately(session_factory, settings):
    job_id = _seed(session_factory, "TEST_PERMANENT", attempts=0)
    _run(process_jobs_once(settings, session_factory))
    after = _get_job(session_factory, job_id)
    assert after.status == JobStatus.FAILED
    assert after.attempts == 0
    assert after.last_error == "doomed"


def test_worker_generic_exception_is_retried(session_factory, settings):
    job_id = _seed(session_factory, "TEST_GENERIC_EXC")
    _run(process_jobs_once(settings, session_factory))
    after = _get_job(session_factory, job_id)
    assert after.status == JobStatus.PENDING
    assert after.attempts == 1
    assert "RuntimeError" in after.last_error


def test_worker_unknown_handler_fails_but_does_not_affect_others(
    session_factory, settings
):
    good_id = _seed(session_factory, "TEST_COMPLETE")
    bad_id = _seed(session_factory, "NO_SUCH_HANDLER")
    processed = _run(process_jobs_once(settings, session_factory))
    assert processed == 2
    assert _get_job(session_factory, good_id).status == JobStatus.COMPLETED
    bad = _get_job(session_factory, bad_id)
    assert bad.status == JobStatus.FAILED
    assert "NO_SUCH_HANDLER" in bad.last_error


def test_worker_processes_multiple_job_types_in_one_batch(session_factory, settings):
    complete_id = _seed(session_factory, "TEST_COMPLETE")
    permanent_id = _seed(session_factory, "TEST_PERMANENT")
    processed = _run(process_jobs_once(settings, session_factory))
    assert processed == 2
    assert _get_job(session_factory, complete_id).status == JobStatus.COMPLETED
    assert _get_job(session_factory, permanent_id).status == JobStatus.FAILED


def test_worker_respects_concurrency_limit(session_factory):
    from core.settings import Settings

    limited = Settings(
        email_max_attempts=5,
        email_retry_base_delay=1,
        email_max_retry_delay=10,
        email_max_concurrency=2,
    )
    for _ in range(5):
        _seed(session_factory, "TEST_SLOW")
    _run(process_jobs_once(limited, session_factory))
    assert CONC_STATE["max_active"] == 2


def test_worker_returns_zero_when_nothing_eligible(session_factory, settings):
    assert _run(process_jobs_once(settings, session_factory)) == 0
