from pathlib import Path

from core.settings import Settings, get_settings
from external_services.email_sender import EmailSender, get_email_sender
from jinja2 import Environment, FileSystemLoader, select_autoescape

WELCOME_SUBJECT = "Welcome to SKYFLARE"

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_welcome_email(recipient: str, *, app_url: str) -> str:
    template = _env.get_template("welcome.html")
    return template.render(recipient=recipient, app_url=app_url)


async def send_welcome_email(
    recipient: str,
    *,
    user_id: str,
    sender: EmailSender | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    sender = sender or get_email_sender(settings)
    html = render_welcome_email(recipient, app_url=settings.app_url)
    await sender.send(recipient=recipient, subject=WELCOME_SUBJECT, html=html)
