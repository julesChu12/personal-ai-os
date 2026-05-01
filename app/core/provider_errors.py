from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class ProviderError(Exception):
    """Base error for external model and embedding provider failures."""


class ProviderConfigurationError(ProviderError, ValueError):
    """Raised when a provider is selected but required configuration is missing."""


class ProviderRequestError(ProviderError):
    """Raised when a provider request fails after retries."""


class ProviderTimeoutError(ProviderRequestError, TimeoutError):
    """Raised when a provider request times out after retries."""


def retry_provider_call(
    operation: Callable[[], T],
    *,
    attempts: int,
    error_message: str,
) -> T:
    """Run a provider operation with bounded retries and sanitized errors."""
    safe_attempts = max(1, int(attempts))
    last_error: Exception | None = None

    for _ in range(safe_attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc

    if _is_timeout_error(last_error):
        raise ProviderTimeoutError(f"{error_message}: provider timed out") from last_error
    raise ProviderRequestError(error_message) from last_error


def _is_timeout_error(exc: Exception | None) -> bool:
    if exc is None:
        return False
    return isinstance(exc, TimeoutError) or "Timeout" in type(exc).__name__
