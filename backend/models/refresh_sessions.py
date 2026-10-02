import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Index, func
from sqlmodel import Field, SQLModel


class RefreshSession(SQLModel, table=True):
    """Server-side session row for one refresh-token generation.

    Rotation inserts a sibling row in the same ``family_id`` and revokes the
    presented row (``revoked_at`` + ``replaced_by``). Presenting a revoked,
    replaced token is reuse: revoke the whole family. ``expires_at`` is copied
    from the family root and never extended on rotation (absolute lifetime).
    """

    __tablename__ = "refresh_sessions"
    __table_args__ = (Index("ix_refresh_sessions_family_id", "family_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", nullable=False, index=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    family_id: uuid.UUID = Field(default_factory=uuid.uuid4, nullable=False)
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), nullable=False, server_default=func.now()
        )
    )
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    last_used_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_at: datetime | None = Field(
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    replaced_by: uuid.UUID | None = Field(default=None, nullable=True)
    user_agent: str | None = Field(default=None, max_length=512, nullable=True)
    ip_address: str | None = Field(default=None, max_length=64, nullable=True)
