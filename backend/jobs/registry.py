from collections.abc import Callable  # type
from typing import TypeVar  # generic type

from jobs.base import JobHandler
from models.outbox import JobType

HandlerClass = TypeVar("HandlerClass", bound=type[JobHandler])

_REGISTRY: dict[str, type[JobHandler]] = {}


def register_handler(
    job_type: JobType | str,
) -> Callable[
    [HandlerClass], HandlerClass
]:  ##Function တစ်ခုရှိတယ်သူက HandlerClass တစ်ခုကို input အနေနဲ့ယူတယ်။HandlerClass တစ်ခုကို ပြန် return လုပ်တယ်။
    key = job_type.value if isinstance(job_type, JobType) else job_type

    def decorator(handler_cls: HandlerClass) -> HandlerClass:
        _REGISTRY[key] = handler_cls
        return handler_cls

    return decorator


def get_handler(job_type: str) -> type[JobHandler]:
    try:
        return _REGISTRY[job_type]
    except KeyError:
        raise KeyError(f"No handler registered for job type {job_type!r}") from None
