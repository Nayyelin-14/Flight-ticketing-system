import uuid

from crud.outbox import SessionFactory
from models.events import ProcessedEvent


def was_processed(
    session_factory: SessionFactory,
    *,
    consumer_group: str,
    event_id: uuid.UUID,
) -> bool:
    with session_factory() as db:
        return db.get(ProcessedEvent, (consumer_group, event_id)) is not None


def mark_processed(
    session_factory: SessionFactory,
    *,
    consumer_group: str,
    event_id: uuid.UUID,
) -> bool:
    """Record an event as processed; returns False if it was already present.

    Atomic on PostgreSQL via ``ON CONFLICT DO NOTHING``; a portable
    check-then-insert fallback is used else (e.g. SQLite tests).
    """
    with session_factory() as db:
        if db.bind is not None and db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            stmt = (
                insert(ProcessedEvent)
                .values(consumer_group=consumer_group, event_id=event_id)
                .on_conflict_do_nothing()
            )
            result = db.execute(stmt)
            db.commit()
            return result.rowcount == 1

        if db.get(ProcessedEvent, (consumer_group, event_id)) is not None:
            return False
        db.add(ProcessedEvent(consumer_group=consumer_group, event_id=event_id))
        db.commit()
        return True
