import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from aiokafka import AIOKafkaConsumer
from aiokafka.structs import OffsetAndMetadata, TopicPartition
from core.settings import Settings
from crud.outbox import SessionFactory
from database import SessionLocal
from events.backoff import backoff_seconds
from events.domains import domain_topic, event_domain
from events.envelope import EventEnvelope, EventJob, deserialize_event
from events.idempotency import mark_processed, was_processed
from events.kafka import (
    Producer,
    build_consumer,
    build_producer,
    dlq_topic,
    retry_topic,
)
from jobs.base import JobPermanentError
from jobs.registry import get_handler

logger = logging.getLogger(__name__)


class MessageLike(Protocol):
    topic: str
    partition: int
    offset: int
    key: Any | None
    value: Any


class EventConsumer:
    """Generic Kafka consumer.

    Flow per message: deserialize envelope -> (if retry topic, backoff) ->
    idempotency check -> dispatch via the handler registry -> idempotency
    record -> offset commit.

    Failures: permanent (``JobPermanentError``, unknown handler, malformed
    envelope) route to the DLQ; transient (``JobRetryError`` / generic) route
    to the retry topic with exponential backoff and move to the DLQ after
    ``KAFKA_MAX_ATTEMPTS``. The offset is only committed after the message was
    handled or safely re-routed, so at-least-once delivery is preserved.
    """

    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory = SessionLocal,
        *,
        topics: list[str],
        group_id: str | None = None,
        producer: Producer | None = None,
        consumer: AIOKafkaConsumer | None = None,
        is_retry: bool = False,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._topics = topics
        self._group_id = group_id or settings.kafka_consumer_group
        self._producer = producer or build_producer(settings)
        self._consumer = consumer or build_consumer(
            settings, topics=topics, group_id=self._group_id
        )
        self._is_retry = is_retry

    async def run(self) -> None:
        """Consume and handle messages until cancelled or the consumer errors."""
        await self._consumer.start()
        try:
            async for message in self._consumer:
                await self._process_message(message)
        finally:
            await self._consumer.stop()

    async def _process_message(self, message: MessageLike) -> None:
        try:
            envelope = deserialize_event(message.value)
        except Exception as exc:  # noqa: BLE001
            await self._handle_malformed(message, exc)
            return

        if self._is_retry:
            delay = backoff_seconds(
                envelope.attempts,
                base=self._settings.kafka_retry_base_delay,
                maximum=self._settings.kafka_max_retry_delay,
            )
            await asyncio.sleep(delay)

        if was_processed(
            self._session_factory,
            consumer_group=self._group_id,
            event_id=envelope.event_id,
        ):
            await self._commit(message)
            return

        job = EventJob(
            id=envelope.event_id,
            job_type=envelope.event_type,
            payload=envelope.payload,
            attempts=envelope.attempts,
        )

        try:
            handler_cls = get_handler(job.job_type)
        except KeyError:
            await self._send_to_dlq(
                message,
                envelope,
                reason=f"no handler for event type {job.job_type!r}",
            )
            await self._commit(message)
            return

        try:
            await handler_cls().handle(job)
        except JobPermanentError as exc:
            await self._send_to_dlq(message, envelope, reason=str(exc))
        except Exception as exc:  # noqa: BLE001
            await self._handle_transient(message, envelope, exc)
            return
        else:
            mark_processed(
                self._session_factory,
                consumer_group=self._group_id,
                event_id=envelope.event_id,
            )
        await self._commit(message)

    def _canonical_topic(self, envelope: EventEnvelope) -> str:
        """The event's owning-domain topic (its canonical source of truth).

        Derived from ``event_type`` rather than the message's actual topic so a
        message replayed from ``users.events-retry`` still resolves back to
        ``users.events`` and never to ``users.events-retry-retry``.
        """
        return domain_topic(event_domain(envelope.event_type))

    def _dlq_topic_for(self, message: MessageLike, envelope: EventEnvelope) -> str:
        try:
            return dlq_topic(self._canonical_topic(envelope))
        except KeyError:
            return dlq_topic(message.topic)

    async def _handle_transient(
        self, message: MessageLike, envelope: EventEnvelope, exc: Exception
    ) -> None:
        next_attempts = envelope.attempts + 1
        retry_envelope = envelope.model_copy(update={"attempts": next_attempts})
        logger.warning(
            "event %s (%s) failed transiently: %s",
            envelope.event_id,
            envelope.event_type,
            exc,
        )
        if next_attempts >= self._settings.kafka_max_attempts:
            await self._send_to_dlq(
                message,
                retry_envelope,
                reason=f"{type(exc).__name__}: {exc}",
            )
        else:
            try:
                target = retry_topic(self._canonical_topic(retry_envelope))
            except KeyError:
                target = retry_topic(message.topic)
            await self._publish(target, retry_envelope)
        await self._commit(message)

    async def _handle_malformed(self, message: MessageLike, exc: Exception) -> None:
        logger.warning("event at %s is undecodable (%s)", message.offset, exc)
        raw = message.value
        event_id = None
        if message.key is not None:
            try:
                event_id = uuid.UUID(str(message.key))
            except ValueError:
                event_id = None
        envelope = EventEnvelope(
            event_id=event_id or uuid.uuid4(),
            event_type="UNKNOWN",
            occurred_at=datetime.now(UTC),
            source=self._settings.kafka_source,
            payload={"raw": bytes(raw).decode("utf-8", errors="replace")[:1000]},
        )
        await self._send_to_dlq(message, envelope, reason=f"undecodable event: {exc}")
        await self._commit(message)

    async def _send_to_dlq(
        self,
        message: MessageLike,
        envelope: EventEnvelope,
        *,
        reason: str,
    ) -> None:
        logger.error(
            "event %s (%s) moved to DLQ: %s",
            envelope.event_id,
            envelope.event_type,
            reason,
        )
        await self._publish(self._dlq_topic_for(message, envelope), envelope)

    async def _publish(self, topic: str, envelope: EventEnvelope) -> None:
        await self._producer.send_and_wait(
            topic,
            key=str(envelope.event_id),
            value=envelope.model_dump(mode="json"),
        )

    async def _commit(self, message: MessageLike) -> None:
        await self._consumer.commit(
            {
                TopicPartition(message.topic, message.partition): OffsetAndMetadata(
                    message.offset + 1, ""
                )
            }
        )
