import asyncio

import aiosmtplib
import pytest
from core.settings import Settings
from external_services import email_sender as email_sender_module
from external_services.email import (
    WELCOME_SUBJECT,
    render_welcome_email,
    send_welcome_email,
)
from external_services.email_sender import (
    EmailSendError,
    NoOpEmailSender,
    PermanentEmailError,
    SMTPEmailSender,
)


class FakeSMTP:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.send_error: Exception | None = None
        self.connect_error: Exception | None = None
        self.connect_called = False
        self.starttls_called = False
        self.login_credentials = None
        self.message = None
        self.quit_called = False

    async def connect(self) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.connect_called = True

    async def starttls(self) -> None:
        self.starttls_called = True

    async def login(self, username, password) -> None:
        self.login_credentials = (username, password)

    async def send_message(self, message) -> None:
        if self.send_error is not None:
            raise self.send_error
        self.message = message

    async def quit(self) -> None:
        self.quit_called = True


def _smtp_sender() -> SMTPEmailSender:
    settings = Settings(
        smtp_host="smtp.example.com",
        smtp_from_email="noreply@example.com",
    )
    return SMTPEmailSender(settings)


def _patch(fake: FakeSMTP, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(email_sender_module.aiosmtplib, "SMTP", lambda **kwargs: fake)


def test_render_welcome_email_contains_name_and_cta():
    html = render_welcome_email(
        "alice@example.com",
        app_url="https://app.example.com",
        verification_url="https://app.example.com/verify-email?token=abc123",
        name="Alice",
    )
    assert "Alice" in html
    assert "https://app.example.com/verify-email?token=abc123" in html
    assert "Verify My Email" in html


def test_render_welcome_email_escapes_html():
    html = render_welcome_email(
        "test@example.com",
        app_url="https://app.example.com",
        verification_url="https://app.example.com/verify-email?token=abc",
        name="<script>alert(1)</script>",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_welcome_subject():
    assert WELCOME_SUBJECT == "Welcome to SKYFLARE"


def test_send_welcome_email_uses_injected_sender():
    class FakeSender:
        durable = True

        def __init__(self) -> None:
            self.sent: list[tuple[str, str, str]] = []

        async def send(self, *, recipient, subject, html) -> None:
            self.sent.append((recipient, subject, html))

    settings = Settings(app_url="https://app.example.com")
    sender = FakeSender()
    asyncio.run(
        send_welcome_email(
            "alice@example.com",
            user_id="user-123",
            verification_token="test-token-abc",
            sender=sender,
            settings=settings,
        )
    )
    recipient, subject, html = sender.sent[0]
    assert recipient == "alice@example.com"
    assert subject == WELCOME_SUBJECT
    assert "user-123" not in html
    assert "verify-email?token=test-token-abc" in html


def test_smtp_send_success(monkeypatch):
    fake = FakeSMTP()
    _patch(fake, monkeypatch)
    sender = _smtp_sender()
    asyncio.run(
        sender.send(
            recipient="bob@example.com",
            subject="Hello",
            html="<p>Body</p>",
        )
    )
    assert fake.connect_called
    assert fake.message is not None
    assert fake.message["To"] == "bob@example.com"
    assert fake.message["From"] == "noreply@example.com"
    assert fake.quit_called


def test_smtp_send_with_login(monkeypatch):
    fake = FakeSMTP()
    _patch(fake, monkeypatch)
    sender = SMTPEmailSender(
        Settings(
            smtp_host="smtp.example.com",
            smtp_from_email="noreply@example.com",
            smtp_username="user",
            smtp_password="secret",
        )
    )
    asyncio.run(sender.send(recipient="bob@example.com", subject="Hi", html="<p>x</p>"))
    assert fake.login_credentials == ("user", "secret")


@pytest.mark.parametrize(
    "error_cls, args, expected",
    [
        (
            aiosmtplib.SMTPRecipientsRefused,
            ({"bob@example.com": (550, "no such user")},),
            PermanentEmailError,
        ),
        (
            aiosmtplib.SMTPAuthenticationError,
            (535, "authentication failed"),
            PermanentEmailError,
        ),
        (aiosmtplib.SMTPResponseException, (452, "try again later"), EmailSendError),
        (OSError, ("connection reset",), EmailSendError),
        (TimeoutError, ("timed out",), EmailSendError),
    ],
)
def test_smtp_error_mapping(monkeypatch, error_cls, args, expected):
    fake = FakeSMTP()
    _patch(fake, monkeypatch)
    sender = _smtp_sender()

    async def attempt():
        fake.send_error = error_cls(*args)
        await sender.send(recipient="bob@example.com", subject="Hi", html="<p>x</p>")

    with pytest.raises(expected):
        asyncio.run(attempt())


def test_smtp_error_mapping_on_connect(monkeypatch):
    fake = FakeSMTP()
    _patch(fake, monkeypatch)
    sender = _smtp_sender()

    async def attempt():
        fake.connect_error = TimeoutError("timed out")
        await sender.send(recipient="bob@example.com", subject="Hi", html="<p>x</p>")

    with pytest.raises(EmailSendError):
        asyncio.run(attempt())


def test_noop_sender_requires_ack():
    strict = NoOpEmailSender(Settings(email_allow_noop_ack=False))
    with pytest.raises(PermanentEmailError):
        asyncio.run(
            strict.send(recipient="bob@example.com", subject="Hi", html="<p>x</p>")
        )


def test_noop_sender_succeeds_when_ack_allowed():
    acked = NoOpEmailSender(Settings(email_allow_noop_ack=True))
    asyncio.run(acked.send(recipient="bob@example.com", subject="Hi", html="<p>x</p>"))


def test_get_email_sender_selects_backend(monkeypatch):
    smtp = email_sender_module.get_email_sender(
        Settings(smtp_host="smtp.example.com", smtp_from_email="n@example.com")
    )
    assert isinstance(smtp, SMTPEmailSender)

    noop = email_sender_module.get_email_sender(Settings(email_backend="noop"))
    assert isinstance(noop, NoOpEmailSender)

    explicit_smtp = email_sender_module.get_email_sender(
        Settings(
            email_backend="smtp",
            smtp_host="smtp.example.com",
            smtp_from_email="n@example.com",
        )
    )
    assert isinstance(explicit_smtp, SMTPEmailSender)

    monkeypatch.setenv("SMTP_HOST", "")
    with pytest.raises(RuntimeError):
        email_sender_module.get_email_sender(Settings(email_backend="smtp"))

    with pytest.raises(ValueError):
        email_sender_module.get_email_sender(Settings(email_backend="bogus"))
