from typing import Annotated

from crud.users import get_user_by_verification_token
from dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from schemas.users import UserCreate, UserResponse
from sqlmodel import Session

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


class VerifyEmailRequest(BaseModel):
    token: str


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(body: UserCreate, db: DbSession) -> dict:
    from routers.users import register as users_register

    return users_register(body, db)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(body: VerifyEmailRequest, db: DbSession) -> dict:
    user = get_user_by_verification_token(db, body.token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid or already used verification token",
            },
        )

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    db.add(user)
    db.commit()

    return {"message": "Email verified successfully"}
