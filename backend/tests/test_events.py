import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from core.settings import Settings
from crud import outbox as outbox_crud
from events import (
    EventConsumer,
    EventEnvelope,
    OutboxPublisher,
    all_domain_topics,
    backoff_seconds,
    deserialize_event,
    dlq_topic,
    domain_topic,
    ensure_topics,
    event_domain,
    event_topic,
    retry_topic,
    serialize_event,
)
from events import domains as event_domains
from events.idempotency import mark_processed, was_processed
from jobs.base import JobPermanentError, JobRetryError
from jobs.registry import register_handler
from models.outbox import JobStatus, JobType

SUCCESS_IDS: list[str] = []
PERMANENT_IDS: list[str] = []
TRANSIENT_IDS: list[str] = []


@register_handler("EVT_SUCCESS")
class SuccessHandler:
    async def handle(self, job) -> None:
        SUCCESS_IDS.append(str(job.id))


@register_handler("EVT_PERMANENT")
class PermanentHandler:
    async def handle(self, job) -> None:
        PERMANENT_IDS.append(str(job.id))
        raise JobPermanentError("doomed")


@register_handler("EVT_TRANSIENT")
class TransientHandler:
    async def handle(self, job) -> None:
        TRANSIENT_IDS.append(str(job.id))
        raise JobRetryError("outage")


for _event_type in (
    "EVT_PUBLISH",
    "EVT_SUCCESS",
    "EVT_PERMANENT",
    "EVT_TRANSIENT",
    "NO_SUCH_EVENT",
):
    event_domains.EVENT_DOMAINS[_event_type] = event_domains.Domain.USERS


@dataclass
class FakeMessage:
    topic: str
    partition: int
    offset: int
    value: bytes
    key: str | None = None


@dataclass
class FakeProducer:
    sent: list[tuple[str, str, dict]] = field(default_factory=list)
    fail_on_send: bool = False

    async def send_and_wait(self, topic: str, *, key: str, value: dict) -> object:
        if self.fail_on_send:
            raise RuntimeError("broker down")
        self.sent.append((topic, key, value))
        return object()


@dataclass
class FakeConsumer:
    committed: list = field(default_factory=list)

    async def commit(self, offsets) -> None:
        self.committed.append(offsets)


@pytest.fixture()
def kafka_settings() -> Settings:
    return Settings(
        kafka_consumer_group="test-group",
        kafka_max_attempts=3,
        kafka_retry_base_delay=1,
        kafka_max_retry_delay=10,
    )


def _envelope(event_type: str = "EVT_SUCCESS", *, attempts: int = 0) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid.uuid4(),
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        source="test",
        attempts=attempts,
        payload={"recipient": "a@b.com"},
    )


def _consumer(
    settings: Settings,
    session_factory,
    *,
    producer: FakeProducer | None = None,
    consumer: FakeConsumer | None = None,
    topics: list[str] | None = None,
    is_retry: bool = False,
) -> tuple[EventConsumer, FakeProducer, FakeConsumer]:
    producer = producer or FakeProducer()
    consumer = consumer or FakeConsumer()
    instance = EventConsumer(
        settings,
        session_factory,
        topics=topics or ["events"],
        producer=producer,
        consumer=consumer,
        is_retry=is_retry,
    )
    return instance, producer, consumer


def _message(envelope: EventEnvelope, *, offset: int = 0) -> FakeMessage:
    return FakeMessage(
        topic="events",
        partition=0,
        offset=offset,
        value=serialize_event(envelope),
        key=str(envelope.event_id),
    )


def _seed_job(session_factory, job_type: str, payload: dict | None = None) -> uuid.UUID:
    with session_factory() as db:
        job = outbox_crud.create_outbox_job(db, job_type, payload or {"k": "v"})
        db.commit()
        return job.id


def _get_job(session_factory, job_id) -> object:
    from models.outbox import OutboxJob

    with session_factory() as db:
        return db.get(OutboxJob, job_id)


def test_backoff_seconds_caps_at_maximum() -> None:
    assert backoff_seconds(1, base=2, maximum=300) == 2
    assert backoff_seconds(2, base=2, maximum=300) == 4
    assert backoff_seconds(10, base=2, maximum=300) == 300


def test_envelope_round_trip() -> None:
    envelope = _envelope()
    restored = deserialize_event(serialize_event(envelope))
    assert restored == envelope


def test_topic_derivation() -> None:
    assert retry_topic("events") == "events-retry"
    assert dlq_topic("events") == "events-dlq"


def test_mark_and_check_processed_is_idempotent(session_factory) -> None:
    event_id = uuid.uuid4()
    assert (
        was_processed(session_factory, consumer_group="g", event_id=event_id) is False
    )
    assert (
        mark_processed(session_factory, consumer_group="g", event_id=event_id) is True
    )
    assert was_processed(session_factory, consumer_group="g", event_id=event_id) is True
    assert (
        mark_processed(session_factory, consumer_group="g", event_id=event_id) is False
    )


def test_domain_routing() -> None:
    assert event_domain(JobType.WELCOME_EMAIL.value) == event_domains.Domain.USERS
    assert event_topic(JobType.WELCOME_EMAIL.value) == "users.events"
    assert domain_topic(event_domains.Domain.USERS) == "users.events"
    assert "users.events" in all_domain_topics()
    with pytest.raises(KeyError):
        event_topic("NO_DOMAIN_EVENT")


def test_publisher_publishes_and_completes_job(session_factory, kafka_settings) -> None:
    job_id = _seed_job(session_factory, JobType.WELCOME_EMAIL.value, {"a": 1})
    producer = FakeProducer()
    publisher = OutboxPublisher(kafka_settings, session_factory, producer=producer)

    published = asyncio.run(publisher.publish_once())

    assert published == 1
    assert _get_job(session_factory, job_id).status == JobStatus.COMPLETED
    topic, key, value = producer.sent[0]
    assert topic == "users.events"
    assert key == str(job_id)
    assert value["event_id"] == str(job_id)
    assert value["event_type"] == "WELCOME_EMAIL"
    assert value["payload"] == {"a": 1}
    assert value["attempts"] == 0


def test_publisher_retries_job_on_publish_failure(
    session_factory, kafka_settings
) -> None:
    job_id = _seed_job(session_factory, "EVT_PUBLISH", {"a": 1})
    producer = FakeProducer(fail_on_send=True)
    publisher = OutboxPublisher(kafka_settings, session_factory, producer=producer)

    asyncio.run(publisher.publish_once())

    assert producer.sent == []
    job = _get_job(session_factory, job_id)
    assert job.status == JobStatus.PENDING
    assert job.attempts == 1
    assert "Kafka publish failed" in job.last_error
    assert job.completed_at is None


def test_publisher_unknown_domain_is_retried_not_sent(
    session_factory, kafka_settings
) -> None:
    job_id = _seed_job(session_factory, "NO_SUCH_DOMAIN_EVENT", {"a": 1})
    producer = FakeProducer()
    publisher = OutboxPublisher(kafka_settings, session_factory, producer=producer)

    asyncio.run(publisher.publish_once())

    assert producer.sent == []
    job = _get_job(session_factory, job_id)
    assert job.status == JobStatus.PENDING
    assert job.attempts == 1
    assert "No domain registered" in job.last_error
    assert job.completed_at is None


def test_publisher_republishes_stale_processing_job(
    session_factory, kafka_settings
) -> None:
    from datetime import timedelta

    from models.outbox import OutboxJob
    from sqlmodel import update

    job_id = _seed_job(session_factory, "EVT_PUBLISH")
    with session_factory() as db:
        db.exec(
            update(OutboxJob)
            .where(OutboxJob.id == job_id)
            .values(
                status=JobStatus.PROCESSING.value,
                updated_at=datetime.now(UTC) - timedelta(minutes=10),
            )
        )
        db.commit()

    producer = FakeProducer()
    publisher = OutboxPublisher(kafka_settings, session_factory, producer=producer)

    published = asyncio.run(publisher.publish_once())

    assert published == 1
    assert _get_job(session_factory, job_id).status == JobStatus.COMPLETED
    assert producer.sent[0][1] == str(job_id)


def test_consumer_success_records_idempotency_and_commits(
    session_factory, kafka_settings
) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    envelope = _envelope()

    asyncio.run(consumer._process_message(_message(envelope)))

    assert SUCCESS_IDS == [str(envelope.event_id)]
    assert was_processed(
        session_factory, consumer_group="test-group", event_id=envelope.event_id
    )
    assert len(fake_consumer.committed) == 1
    assert producer.sent == []

    asyncio.run(consumer._process_message(_message(envelope, offset=1)))
    assert SUCCESS_IDS == [str(envelope.event_id)]
    assert len(fake_consumer.committed) == 2


def test_consumer_permanent_error_goes_to_dlq(session_factory, kafka_settings) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    envelope = _envelope("EVT_PERMANENT")

    asyncio.run(consumer._process_message(_message(envelope)))

    topic, key, value = producer.sent[0]
    assert topic == "users.events-dlq"
    assert key == str(envelope.event_id)
    assert value["event_type"] == "EVT_PERMANENT"
    assert len(fake_consumer.committed) == 1
    assert not was_processed(
        session_factory, consumer_group="test-group", event_id=envelope.event_id
    )


def test_consumer_transient_error_goes_to_retry_topic(
    session_factory, kafka_settings
) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    envelope = _envelope("EVT_TRANSIENT")

    asyncio.run(consumer._process_message(_message(envelope)))

    assert len(producer.sent) == 1
    topic, key, value = producer.sent[0]
    assert topic == "users.events-retry"
    assert key == str(envelope.event_id)
    assert value["event_type"] == "EVT_TRANSIENT"
    assert value["attempts"] == 1
    assert len(fake_consumer.committed) == 1


def test_retry_consumer_rerequeues_to_same_retry_topic(
    session_factory, kafka_settings
) -> None:
    consumer, producer, fake_consumer = _consumer(
        kafka_settings, session_factory, is_retry=True
    )
    envelope = _envelope("EVT_TRANSIENT", attempts=0)
    message = _message(envelope)
    message.topic = "users.events-retry"

    asyncio.run(consumer._process_message(message))

    topic, key, value = producer.sent[0]
    assert topic == "users.events-retry"
    assert topic != "users.events-retry-retry"
    assert key == str(envelope.event_id)
    assert value["attempts"] == 1
    assert len(fake_consumer.committed) == 1


def test_consumer_exhausted_retries_go_to_dlq(session_factory, kafka_settings) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    envelope = _envelope("EVT_TRANSIENT", attempts=2)

    asyncio.run(consumer._process_message(_message(envelope)))

    assert len(producer.sent) == 1
    topic, _, value = producer.sent[0]
    assert topic == "users.events-dlq"
    assert value["attempts"] == 3
    assert len(fake_consumer.committed) == 1


def test_consumer_unknown_handler_goes_to_dlq(session_factory, kafka_settings) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    envelope = _envelope("NO_SUCH_EVENT")

    asyncio.run(consumer._process_message(_message(envelope)))

    assert producer.sent[0][0] == "users.events-dlq"
    assert len(fake_consumer.committed) == 1
    assert not was_processed(
        session_factory, consumer_group="test-group", event_id=envelope.event_id
    )


def test_consumer_malformed_event_goes_to_dlq(session_factory, kafka_settings) -> None:
    consumer, producer, fake_consumer = _consumer(kafka_settings, session_factory)
    key = str(uuid.uuid4())
    # No event_type to recover a domain from: DLQ falls back to message.topic.
    message = FakeMessage(
        topic="events", partition=0, offset=7, value=b"not json", key=key
    )

    asyncio.run(consumer._process_message(message))

    assert len(producer.sent) == 1
    topic, sent_key, value = producer.sent[0]
    assert topic == "events-dlq"
    assert sent_key == key
    assert value["event_type"] == "UNKNOWN"
    assert len(fake_consumer.committed) == 1


def test_consumer_does_not_commit_when_rerouting_fails(
    session_factory, kafka_settings
) -> None:
    producer = FakeProducer(fail_on_send=True)
    consumer, _, fake_consumer = _consumer(
        kafka_settings, session_factory, producer=producer
    )
    envelope = _envelope("EVT_TRANSIENT")

    with pytest.raises(RuntimeError, match="broker down"):
        asyncio.run(consumer._process_message(_message(envelope)))

    assert fake_consumer.committed == []


@dataclass
class FakeAdminClient:
    existing: set[str]
    created: list[str] = field(default_factory=list)

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def list_topics(self) -> set[str]:
        return self.existing

    async def create_topics(self, new_topics) -> None:
        for topic in new_topics:
            self.existing.add(topic.name)
            self.created.append(topic.name)


def test_ensure_topics_provisions_idempotently() -> None:
    domains = all_domain_topics()
    expected = sorted(
        {*domains, *(retry_topic(t) for t in domains), *(dlq_topic(t) for t in domains)}
    )
    admin = FakeAdminClient(existing=set())
    settings = Settings(
        kafka_bootstrap_servers="localhost:9092",
        kafka_topic_partitions=1,
        kafka_topic_replication=1,
    )

    created_first = asyncio.run(ensure_topics(settings, admin_client=admin))
    created_second = asyncio.run(ensure_topics(settings, admin_client=admin))

    assert created_first == expected
    assert created_second == []
    assert sorted(admin.created) == expected
    assert admin.existing == set(expected)
