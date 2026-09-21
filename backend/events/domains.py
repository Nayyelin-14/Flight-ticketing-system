"""Domain ownership and Kafka topic routing.

``JobType`` in ``models/outbox.py`` is the single event catalog; this module
is the single routing map that assigns each event to its owning domain. Topic
names are derived by convention (``{domain}.events``) so producer routing,
consumer subscriptions, and startup provisioning all agree without duplicating
topic names anywhere else.
"""

from enum import StrEnum

from models.outbox import JobType


class Domain(StrEnum):
    USERS = "users"
    BOOKING = "booking"
    PAYMENT = "payment"


EVENT_DOMAINS: dict[str, Domain] = {
    JobType.WELCOME_EMAIL.value: Domain.USERS,
}


def domain_topic(domain: Domain) -> str:
    """Canonical topic for a domain: ``{domain}.events``."""
    return f"{domain}.events"


def event_domain(event_type: str) -> Domain:
    """Return the owning domain for an event type.

    Raises ``KeyError`` for unregistered event types so producers fail loud
    instead of silently routing to a wrong topic.
    """
    try:
        return EVENT_DOMAINS[event_type]
    except KeyError:
        raise KeyError(f"No domain registered for event type {event_type!r}") from None


def event_topic(event_type: str) -> str:
    """Topic an event is published to: its owning domain's topic."""
    return domain_topic(event_domain(event_type))


def all_domain_topics() -> list[str]:
    """Every domain topic for domains that currently own at least one event.

    Consumers and provisioning derive their subscription/creation sets from
    this list, so adding a new domain registers it everywhere at once.
    """
    return sorted({domain_topic(domain) for domain in EVENT_DOMAINS.values()})
