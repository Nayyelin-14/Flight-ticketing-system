from crud import outbox as outbox_crud
from models.outbox import JobType
from models.users import User
from schemas.users import UserCreate
from sqlmodel import Session, select
from utils.authentication import hash_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.exec(select(User).where(User.email == email)).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        email=user_in.email,
        password_hash=hash_password(user_in.password),
    )
    db.add(user)
    db.flush()
    outbox_crud.create_outbox_job(
        db,
        job_type=JobType.WELCOME_EMAIL.value,
        payload={
            "recipient": user_in.email,
            "user_id": str(user.id),
        },
    )
    db.commit()
    db.refresh(user)
    return user
