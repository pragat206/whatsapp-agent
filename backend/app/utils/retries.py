"""Retry decorator for provider calls."""
from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class ProviderTransientError(Exception):
    """Retryable error from an external provider (5xx, timeouts, connection)."""


class ProviderPermanentError(Exception):
    """Non-retryable error from an external provider (4xx, auth, validation)."""


def with_retry(attempts: int = 4):
    return retry(
        reraise=True,
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(ProviderTransientError),
    )
