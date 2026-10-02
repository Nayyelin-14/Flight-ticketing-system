from pydantic import BaseModel, EmailStr, field_validator


def normalize_email(value: str) -> str:
    return value.strip().lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_email(value)


class AuthUserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str


class LoginResponse(BaseModel):
    user: AuthUserResponse


class RefreshResponse(BaseModel):
    user: AuthUserResponse | None = None


class MeResponse(BaseModel):
    user: AuthUserResponse
