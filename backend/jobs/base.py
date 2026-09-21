import uuid
from typing import Any, Protocol


class JobLike(Protocol):
    """Minimal surface handlers rely on, satisfied by ``OutboxJob`` and
    ``EventJob`` so one handler set drives both delivery mechanisms."""

    id: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    attempts: int


class JobPermanentError(Exception):
    """The job can never succeed and should be marked failed immediately."""


class JobRetryError(Exception):
    """The job failed temporarily and should be retried with backoff."""


class JobHandler(Protocol):
    async def handle(self, job: JobLike) -> None: ...
