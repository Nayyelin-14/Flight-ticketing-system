from typing import Annotated

from crud.users import create_user, get_user_by_email
from dependencies import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models.users import User
from schemas.users import UserCreate, UserResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post(
    "/register/", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register(user_in: UserCreate, db: DbSession) -> User:
    if get_user_by_email(db, user_in.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "Email is already registered",
            },
        )

    try:
        return create_user(db, user_in)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": "Email is already registered",
            },
        )
