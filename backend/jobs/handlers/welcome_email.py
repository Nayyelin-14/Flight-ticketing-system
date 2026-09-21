from core.settings import Settings, get_settings
from external_services.email import send_welcome_email
from external_services.email_sender import (
    EmailSender,
    EmailSendError,
    PermanentEmailError,
    get_email_sender,
)
from jobs.base import JobPermanentError, JobRetryError
from jobs.registry import register_handler
from models.outbox import JobType, OutboxJob


@register_handler(JobType.WELCOME_EMAIL)
class WelcomeEmailHandler:
    def __init__(
        self, *, settings: Settings | None = None, sender: EmailSender | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._sender = sender or get_email_sender(self._settings)

    async def handle(self, job: OutboxJob) -> None:
        recipient = job.payload["recipient"]
        user_id = str(job.payload["user_id"])
        verification_token = job.payload["verification_token"]
        try:
            await send_welcome_email(
                recipient,
                user_id=user_id,
                verification_token=verification_token,
                sender=self._sender,
                settings=self._settings,
            )
        except PermanentEmailError as exc:
            raise JobPermanentError(str(exc)) from exc
        except EmailSendError as exc:
            raise JobRetryError(str(exc)) from exc
