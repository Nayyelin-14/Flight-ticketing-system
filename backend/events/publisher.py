import asyncio
import logging

from core.settings import Settings
from crud import outbox as outbox_crud
from crud.outbox import SessionFactory
from database import SessionLocal
from events.backoff import backoff_seconds
from events.domains import event_topic
from events.envelope import EventEnvelope
from events.kafka import Producer, build_producer
from models.outbox import OutboxJob

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Generic outbox -> Kafka publisher.

    Claims eligible outbox rows with ``FOR UPDATE SKIP LOCKED``, publishes a
    generic event to Kafka, and only marks the row COMPLETED after the broker
    acknowledges the write. Publish failures schedule a retry with backoff.

    At-least-once: the outbox row id is used as both the message key and the
    event id, so a crash between "publish acknowledged" and "mark completed"
    results in a re-publish of the *same* event id, which downstream consumers
    can de-duplicate.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory = SessionLocal,
        *,
        producer: Producer | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._producer = producer or build_producer(settings)

    async def publish_once(self) -> int:
        outbox_crud.recover_stale_jobs(
            self._session_factory,
            processing_timeout_seconds=self._settings.kafka_processing_timeout,
        )
        jobs = outbox_crud.claim_eligible_jobs(
            self._session_factory,
            batch_size=self._settings.kafka_publish_batch_size,
        )
        if not jobs:
            return 0

        semaphore = asyncio.Semaphore(self._settings.kafka_publish_concurrency)

        async def _run(job: OutboxJob) -> None:
            async with semaphore:
                await self._publish_job(job)

        await asyncio.gather(*(_run(job) for job in jobs))
        return len(jobs)

    async def _publish_job(self, job: OutboxJob) -> None:
        envelope = EventEnvelope(
            event_id=job.id,
            event_type=job.job_type,
            occurred_at=job.created_at,
            source=self._settings.kafka_source,
            payload=job.payload,
        )
        try:
            topic = event_topic(job.job_type)
        except KeyError:
            delay = backoff_seconds(
                job.attempts + 1,
                base=self._settings.kafka_publish_base_delay,
                maximum=self._settings.kafka_publish_max_delay,
            )
            outbox_crud.schedule_retry(
                self._session_factory,
                job=job,
                delay_seconds=delay,
                error=f"No domain registered for event type {job.job_type!r}",
            )
            return
        try:
            await self._producer.send_and_wait(
                topic,
                key=str(job.id),
                value=envelope.model_dump(mode="json"),
            )
        except Exception as exc:  # noqa: BLE001
            delay = backoff_seconds(
                job.attempts + 1,
                base=self._settings.kafka_publish_base_delay,
                maximum=self._settings.kafka_publish_max_delay,
            )
            outbox_crud.schedule_retry(
                self._session_factory,
                job=job,
                delay_seconds=delay,
                error=f"Kafka publish failed: {type(exc).__name__}: {exc}",
            )
            return
        outbox_crud.mark_completed(self._session_factory, job_id=job.id)

    async def run(self) -> None:
        """Long-running loop: publish eligible events until cancelled."""
        await self._producer.start()
        try:
            while True:
                try:
                    published = await self.publish_once()
                    if published:
                        logger.info("published %s outbox event(s)", published)
                except Exception:
                    logger.exception("publisher iteration failed")
                await asyncio.sleep(self._settings.kafka_poll_interval)
        finally:
            await self._producer.stop()
