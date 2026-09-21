import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Generic event envelope shared by every event type.

    ``event_id`` is the stable outbox record id: it is used both as the
    Kafka message key (partitioning / ordering) and as the idempotency key
    for consumer-side at-least-once deduplication.
    """

    event_id: uuid.UUID
    event_type: str
    occurred_at: datetime
    source: str
    attempts: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class EventJob:
    """Adapter handed to handlers so they stay agnostic of delivery mechanism.

    Mirrors the fields of ``OutboxJob`` that ``JobHandler`` implementations
    rely on, so one handler set drives both the polling worker and Kafka.
    """

    id: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    attempts: int


def serialize_event(envelope: EventEnvelope) -> bytes:
    """Serialize an envelope for the Kafka wire format (JSON)."""
    return json.dumps(envelope.model_dump(mode="json")).encode("utf-8")


def deserialize_event(data: bytes | dict[str, Any]) -> EventEnvelope:
    """Parse an envelope from raw bytes or an already-decoded JSON mapping."""
    raw = json.loads(data) if isinstance(data, bytes) else data
    return EventEnvelope.model_validate(raw)
