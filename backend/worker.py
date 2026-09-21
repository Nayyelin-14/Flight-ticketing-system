import asyncio
import logging

from core.settings import Settings, get_settings
from database import SessionLocal
from events.domains import all_domain_topics
from events.kafka import build_producer, ensure_topics, retry_topic


async def _run_kafka(settings: Settings) -> None:
    from events.consumer import EventConsumer
    from events.publisher import OutboxPublisher

    if settings.kafka_provision_topics:
        await ensure_topics(settings)

    producer = build_producer(settings)
    await producer.start()
    try:
        topics = all_domain_topics()
        publisher = OutboxPublisher(settings, SessionLocal)
        main_consumer = EventConsumer(
            settings,
            SessionLocal,
            topics=topics,
            producer=producer,
        )
        retry_consumer = EventConsumer(
            settings,
            SessionLocal,
            topics=[retry_topic(topic) for topic in topics],
            producer=producer,
            is_retry=True,
        )
        await asyncio.gather(publisher.run(), main_consumer.run(), retry_consumer.run())
    finally:
        await producer.stop()


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if settings.kafka_enabled:
        await _run_kafka(settings)
    else:
        from jobs.worker import run_worker

        await run_worker(settings, SessionLocal)


if __name__ == "__main__":
    asyncio.run(main())
