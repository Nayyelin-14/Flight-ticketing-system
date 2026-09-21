import uuid
from datetime import datetime

from pydantic import ConfigDict, EmailStr, field_validator
from sqlmodel import Field, SQLModel


class UserCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserResponse(SQLModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
