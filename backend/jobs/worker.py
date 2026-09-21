import asyncio
import logging

from core.settings import Settings
from crud import outbox as outbox_crud
from crud.outbox import SessionFactory
from events.backoff import backoff_seconds
from jobs import handlers  # noqa: F401
from jobs.base import JobPermanentError, JobRetryError
from jobs.registry import get_handler
from models.outbox import OutboxJob

logger = logging.getLogger(__name__)


async def _handle_retry(
    session_factory: SessionFactory,
    settings: Settings,
    job: OutboxJob,
    error: str,
) -> None:
    next_attempt = job.attempts + 1
    if next_attempt >= settings.email_max_attempts:
        outbox_crud.mark_failed(session_factory, job_id=job.id, error=error)
        return
    delay = backoff_seconds(
        next_attempt,
        base=settings.email_retry_base_delay,
        maximum=settings.email_max_retry_delay,
    )
    outbox_crud.schedule_retry(
        session_factory, job=job, delay_seconds=delay, error=error
    )


async def _process_job(
    session_factory: SessionFactory,
    settings: Settings,
    job: OutboxJob,
) -> None:
    try:
        handler_cls = get_handler(job.job_type)
    except KeyError:
        outbox_crud.mark_failed(
            session_factory,
            job_id=job.id,
            error=f"Unknown job type {job.job_type!r}",
        )
        return

    try:
        await handler_cls().handle(job)
    except JobPermanentError as exc:
        outbox_crud.mark_failed(session_factory, job_id=job.id, error=str(exc))
    except JobRetryError as exc:
        await _handle_retry(session_factory, settings, job, str(exc))
    except Exception as exc:  # noqa: BLE001
        await _handle_retry(
            session_factory, settings, job, f"{type(exc).__name__}: {exc}"
        )
    else:
        outbox_crud.mark_completed(session_factory, job_id=job.id)


async def process_jobs_once(
    settings: Settings,
    session_factory: SessionFactory,
) -> int:
    jobs = outbox_crud.claim_eligible_jobs(
        session_factory, batch_size=settings.email_batch_size
    )
    if not jobs:
        return 0

    semaphore = asyncio.Semaphore(settings.email_max_concurrency)

    async def _run(job: OutboxJob) -> None:
        async with semaphore:
            await _process_job(session_factory, settings, job)

    await asyncio.gather(*(_run(job) for job in jobs))
    return len(jobs)


async def run_worker(
    settings: Settings,
    session_factory: SessionFactory,
) -> None:
    while True:
        try:
            outbox_crud.recover_stale_jobs(
                session_factory,
                processing_timeout_seconds=settings.email_processing_timeout,
            )
            processed = await process_jobs_once(settings, session_factory)
            if processed:
                logger.info("processed %s outbox job(s)", processed)
        except Exception:
            logger.exception("worker iteration failed")
        await asyncio.sleep(settings.email_poll_interval)
