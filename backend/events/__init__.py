"""Generic Kafka event infrastructure.

Transactional outbox -> publisher -> Kafka -> consumer -> handler registry.
Domain-based topics (``{domain}.events``): each domain owns one topic that
carries all of its events. Broker-agnostic: works with Confluent Cloud,
Apache Kafka, or any Kafka-compatible broker via standard configuration.
"""

from events.backoff import backoff_seconds
from events.consumer import EventConsumer
from events.domains import (
    all_domain_topics,
    domain_topic,
    event_domain,
    event_topic,
)
from events.envelope import EventEnvelope, EventJob, deserialize_event, serialize_event
from events.idempotency import mark_processed, was_processed
from events.kafka import (
    Producer,
    build_admin_client,
    build_consumer,
    build_producer,
    dlq_topic,
    ensure_topics,
    retry_topic,
)
from events.publisher import OutboxPublisher

__all__ = [
    "EventConsumer",
    "EventEnvelope",
    "EventJob",
    "OutboxPublisher",
    "Producer",
    "all_domain_topics",
    "backoff_seconds",
    "build_admin_client",
    "build_consumer",
    "build_producer",
    "deserialize_event",
    "dlq_topic",
    "domain_topic",
    "ensure_topics",
    "event_domain",
    "event_topic",
    "mark_processed",
    "retry_topic",
    "serialize_event",
    "was_processed",
]
