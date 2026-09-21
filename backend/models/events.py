import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel


class ProcessedEvent(SQLModel, table=True):
    __tablename__ = "processed_events"

    consumer_group: str = Field(primary_key=True, max_length=128)
    event_id: uuid.UUID = Field(primary_key=True)
    processed_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
    )
