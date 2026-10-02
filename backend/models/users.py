import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(default="", max_length=255)
    email: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)
    is_verified: bool = Field(default=False, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    verification_token: str | None = Field(default=None, max_length=64, nullable=True)
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
