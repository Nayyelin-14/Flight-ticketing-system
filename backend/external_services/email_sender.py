from contextlib import suppress
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib
from core.settings import Settings


class PermanentEmailError(Exception):
    """The email can never be sent (bad recipient, auth/config failure)."""


class EmailSendError(Exception):
    """Transient send failure; the email may not have reached the recipient."""


class EmailSender(Protocol):
    durable: bool

    async def send(self, *, recipient: str, subject: str, html: str) -> None: ...


class SMTPEmailSender:
    durable = True

    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host or not settings.smtp_from_email:
            raise RuntimeError("SMTPEmailSender requires SMTP_HOST and SMTP_FROM_EMAIL")
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._from_email = settings.smtp_from_email
        self._use_tls = settings.smtp_starttls

    async def send(self, *, recipient: str, subject: str, html: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content("Please view this email in an HTML-capable reader.")
        message.add_alternative(html, subtype="html")

        client = aiosmtplib.SMTP(hostname=self._host, port=self._port, timeout=30)
        try:
            await client.connect()
            if self._username:
                await client.login(self._username, self._password)
            await client.send_message(message)
        except (
            aiosmtplib.SMTPRecipientsRefused,
            aiosmtplib.SMTPAuthenticationError,
        ) as exc:
            raise PermanentEmailError(str(exc)) from exc
        except aiosmtplib.SMTPException as exc:
            raise EmailSendError(f"SMTP error: {exc}") from exc
        except (OSError, TimeoutError) as exc:
            raise EmailSendError(f"Network error: {exc}") from exc
        finally:
            with suppress(Exception):
                await client.quit()


class NoOpEmailSender:
    durable = False

    def __init__(self, settings: Settings) -> None:
        self._allow_ack = settings.email_allow_noop_ack

    async def send(self, *, recipient: str, subject: str, html: str) -> None:
        if not self._allow_ack:
            raise PermanentEmailError(
                "No durable email backend configured and EMAIL_ALLOW_NOOP_ACK "
                "is false; job not marked completed"
            )


def get_email_sender(settings: Settings) -> EmailSender:
    backend = settings.resolved_email_backend
    if backend == "smtp":
        return SMTPEmailSender(settings)
    if backend == "noop":
        return NoOpEmailSender(settings)
    raise ValueError(f"Unknown email backend: {backend!r}")
