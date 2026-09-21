import asyncio
import logging
import signal

from core.settings import Settings, get_settings
from database import SessionLocal
from events.domains import all_domain_topics
from events.kafka import build_producer, ensure_topics, retry_topic

logger = logging.getLogger(__name__)


async def _run_kafka(settings: Settings) -> None:
    import jobs.handlers  # noqa: F401 — register all handlers
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

        loop = asyncio.get_running_loop()
        stop = loop.create_future()

        def _signal_handler() -> None:
            if not stop.done():
                stop.set_result(None)

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _signal_handler)

        tasks = [
            asyncio.create_task(publisher.run()),
            asyncio.create_task(main_consumer.run()),
            asyncio.create_task(retry_consumer.run()),
        ]
        await stop
        logger.info("Shutting down gracefully...")
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await producer.stop()
        logger.info("Worker stopped.")


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
