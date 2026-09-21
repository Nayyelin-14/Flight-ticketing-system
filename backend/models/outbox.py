import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Column, DateTime, Index, func
from sqlmodel import Field, SQLModel


class JobStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobType(StrEnum):
    WELCOME_EMAIL = "WELCOME_EMAIL"


class OutboxJob(SQLModel, table=True):
    __tablename__ = "outbox"
    __table_args__ = (
        Index("ix_outbox_status_next_attempt", "status", "next_attempt_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_type: str = Field(max_length=64)
    payload: dict = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default=JobStatus.PENDING.value, max_length=16)
    attempts: int = Field(default=0)
    next_attempt_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
    )
    last_error: str | None = Field(default=None, max_length=1000)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )
    completed_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
