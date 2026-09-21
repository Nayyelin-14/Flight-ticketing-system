def backoff_seconds(attempt: int, *, base: int, maximum: int) -> int:
    """Exponential backoff capped at ``maximum`` seconds."""
    return min(base * (2 ** (attempt - 1)), maximum)
