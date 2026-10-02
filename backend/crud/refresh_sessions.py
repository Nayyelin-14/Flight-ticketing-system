import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from models.refresh_sessions import RefreshSession
from models.users import User
from utils.tokens import generate_refresh_token, hash_refresh_token


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def start_session(
    db: Session,
    user: User,
    *,
    ttl_seconds: int,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, RefreshSession]:
    """Create the family-root refresh session. Returns (raw_token, session)."""
    raw = generate_refresh_token()
    now = datetime.now(UTC)
    session = RefreshSession(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        family_id=uuid.uuid4(),
        expires_at=now + timedelta(seconds=ttl_seconds),
        created_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.flush()
    return raw, session


def get_session_by_raw_token(db: Session, raw_token: str) -> RefreshSession | None:
    stmt = select(RefreshSession).where(
        RefreshSession.token_hash == hash_refresh_token(raw_token)
    )
    return db.execute(stmt).scalars().first()


def lock_session(db: Session, session: RefreshSession) -> RefreshSession | None:
    """Re-read the row with a row lock when the dialect supports it."""
    dialect = db.bind.dialect.name if db.bind is not None else ""
    stmt = select(RefreshSession).where(RefreshSession.id == session.id)
    if dialect == "postgresql":
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalars().first()


def rotate_session(
    db: Session,
    presented: RefreshSession,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, RefreshSession]:
    """Atomically replace presented token with a sibling in the same family.

    Absolute ``expires_at`` is copied from the presented row (never extended).
    """
    now = datetime.now(UTC)
    raw = generate_refresh_token()
    replacement = RefreshSession(
        user_id=presented.user_id,
        token_hash=hash_refresh_token(raw),
        family_id=presented.family_id,
        expires_at=_as_utc(presented.expires_at),
        created_at=now,
        user_agent=user_agent if user_agent is not None else presented.user_agent,
        ip_address=ip_address if ip_address is not None else presented.ip_address,
    )
    db.add(replacement)
    db.flush()
    presented.revoked_at = now
    presented.replaced_by = replacement.id
    presented.last_used_at = now
    db.add(presented)
    db.flush()
    return raw, replacement


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.family_id == family_id)
        .where(RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def revoke_session(db: Session, session: RefreshSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.add(session)


def revoke_by_session_id(db: Session, session_id: uuid.UUID) -> None:
    session = db.get(RefreshSession, session_id)
    if session is not None:
        revoke_family(db, session.family_id)


def purge_expired(db: Session) -> None:
    now = datetime.now(UTC)
    db.execute(
        delete(RefreshSession).where(
            RefreshSession.expires_at < now - timedelta(days=1)
        )
    )
