"""
Retry decorators and error classification for the enrichment pipeline.

Uses ``tenacity`` for bounded exponential-backoff retries.  Permanent
errors (404, invalid domain, etc.) are never retried.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Custom exception hierarchy
# ---------------------------------------------------------------------------


class EnrichmentError(Exception):
    """Base class for all pipeline errors."""


class NetworkError(EnrichmentError):
    """DNS failure, connection refused, or similar network-level error."""


class TimeoutError(EnrichmentError):  # noqa: A001
    """Page or request timed out."""


class HTTPError(EnrichmentError):
    """HTTP error response (4xx / 5xx)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BrowserError(EnrichmentError):
    """Playwright-specific error."""


class ParsingError(EnrichmentError):
    """HTML / JSON parsing failure."""


class LLMError(EnrichmentError):
    """OpenAI API error or invalid response."""


class ValidationError(EnrichmentError):
    """Pydantic model validation failure."""


class PermanentError(EnrichmentError):
    """
    Error that must NOT be retried (e.g., 404, invalid domain).
    Raising this inside a retry context immediately stops retrying.
    """


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


_TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    NetworkError,
    TimeoutError,
    LLMError,
    # Also handle raw httpx / playwright transients that slip through.
    httpx.TimeoutException,
    httpx.ConnectError,
)


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Tenacity before-sleep callback – logs each retry attempt."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry attempt %d/%s after %s: %s",
        retry_state.attempt_number,
        retry_state.retry_object.stop.max_attempt_number,  # type: ignore[attr-defined]
        f"{retry_state.outcome_timestamp - retry_state.start_time:.1f}s elapsed",
        exc,
    )


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
) -> Callable[[F], F]:
    """
    Decorator factory for bounded exponential-backoff retry.

    Only retries :class:`_TRANSIENT_EXCEPTIONS`.  Permanent errors and
    unknown exceptions propagate immediately.

    Parameters
    ----------
    max_attempts:
        Total number of attempts (1 = no retry).
    min_wait, max_wait:
        Bounds for the exponential back-off wait in seconds.
    """

    def decorator(func: F) -> F:
        @retry(
            retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            before_sleep=_log_retry_attempt,
            reraise=True,
        )
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return async_wrapper  # type: ignore[return-value]

    return decorator


def classify_playwright_error(exc: Exception) -> EnrichmentError:
    """
    Convert a raw Playwright exception into a typed pipeline error.

    Parameters
    ----------
    exc:
        The caught exception from Playwright.

    Returns
    -------
    EnrichmentError
        A typed error appropriate to the failure mode.
    """
    from playwright.async_api import Error as PlaywrightError  # noqa: PLC0415
    from playwright.async_api import TimeoutError as PlaywrightTimeout  # noqa: PLC0415

    if isinstance(exc, PlaywrightTimeout):
        return TimeoutError(str(exc))
    if isinstance(exc, PlaywrightError):
        msg = str(exc).lower()
        if "net::err_name_not_resolved" in msg or "dns" in msg:
            return NetworkError(str(exc))
        if "net::err_connection_refused" in msg or "connection" in msg:
            return NetworkError(str(exc))
        return BrowserError(str(exc))
    return EnrichmentError(str(exc))
