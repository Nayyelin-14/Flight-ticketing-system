import json
import logging
import ssl
from typing import Protocol

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.admin import AIOKafkaAdminClient
from aiokafka.admin.new_topic import NewTopic
from aiokafka.errors import TopicAlreadyExistsError
from core.settings import Settings
from events.domains import all_domain_topics

logger = logging.getLogger(__name__)


class Producer(Protocol):
    async def send_and_wait(self, topic: str, *, key: str, value: dict) -> object: ...


def retry_topic(topic: str) -> str:
    return f"{topic}-retry"


def dlq_topic(topic: str) -> str:
    return f"{topic}-dlq"


def _require_broker(settings: Settings) -> None:
    if not settings.kafka_broker_configured:
        raise RuntimeError("KAFKA_ENABLED requires KAFKA_BOOTSTRAP_SERVERS to be set")


def _build_ssl_context(settings: Settings) -> ssl.SSLContext:
    """Create an SSL context, loading Aiven's CA certificate if available."""
    ctx = ssl.create_default_context()
    cafile = getattr(settings, "kafka_ssl_cafile", None)
    if cafile:
        ctx.load_verify_locations(cafile)
    return ctx


def build_producer(settings: Settings) -> AIOKafkaProducer:
    """Build a producer from environment config (broker-agnostic)."""
    _require_broker(settings)
    return AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        security_protocol=settings.kafka_security_protocol,
        sasl_mechanism=settings.kafka_sasl_mechanism,
        sasl_plain_username=settings.kafka_sasl_username or None,
        sasl_plain_password=settings.kafka_sasl_password or None,
        ssl_context=_build_ssl_context(settings),
        key_serializer=lambda key: key.encode("utf-8"),
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )


def build_consumer(
    settings: Settings, *, topics: list[str], group_id: str
) -> AIOKafkaConsumer:
    """Build a consumer from environment config (broker-agnostic).

    Values are left as raw bytes; decoding is the caller's responsibility so
    malformed/undecodable messages can be routed to the DLQ instead of
    crashing the fetch loop.
    """
    _require_broker(settings)
    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        security_protocol=settings.kafka_security_protocol,
        sasl_mechanism=settings.kafka_sasl_mechanism,
        sasl_plain_username=settings.kafka_sasl_username or None,
        sasl_plain_password=settings.kafka_sasl_password or None,
        ssl_context=_build_ssl_context(settings),
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )


def build_admin_client(settings: Settings) -> AIOKafkaAdminClient:
    """Build an admin client for idempotent topic provisioning."""
    _require_broker(settings)
    return AIOKafkaAdminClient(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        security_protocol=settings.kafka_security_protocol,
        sasl_mechanism=settings.kafka_sasl_mechanism,
        sasl_plain_username=settings.kafka_sasl_username or None,
        sasl_plain_password=settings.kafka_sasl_password or None,
        ssl_context=_build_ssl_context(settings),
    )


def _provisioning_topics() -> list[str]:
    """Domain topics plus their retry/DLQ companions, all in one set."""
    domains = all_domain_topics()
    return sorted(
        {*domains, *(retry_topic(t) for t in domains), *(dlq_topic(t) for t in domains)}
    )


async def ensure_topics(
    settings: Settings,
    *,
    admin_client: AIOKafkaAdminClient | None = None,
) -> list[str]:
    """Idempotently create missing domain/retry/DLQ topics.

    Runs once at worker startup, never on publish. Topics that already exist
    are left untouched; concurrent creation races surface as
    ``TopicAlreadyExistsError`` and are tolerated. Pass a pre-built
    ``admin_client`` to share an existing connection (and its lifecycle).
    """
    _require_broker(settings)
    topics = _provisioning_topics()
    client = admin_client or build_admin_client(settings)
    owns_client = admin_client is None
    created: list[str] = []
    try:
        await client.start()
        existing = await client.list_topics()
        missing = [topic for topic in topics if topic not in existing]
        if missing:
            new_topics = [
                NewTopic(
                    name=topic,
                    num_partitions=settings.kafka_topic_partitions,
                    replication_factor=settings.kafka_topic_replication,
                )
                for topic in missing
            ]
            try:
                await client.create_topics(new_topics)
            except TopicAlreadyExistsError:
                logger.info("topics %s were already created concurrently", missing)
            created = missing
    finally:
        if owns_client:
            await client.close()
    return created
