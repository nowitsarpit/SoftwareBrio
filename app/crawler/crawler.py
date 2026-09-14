"""
Async web crawler using Playwright.

Responsibilities:
- Fetch a single page using Playwright (with retry + cache integration).
- Fall back to httpx for pages that block Playwright.
- Return a :class:`PageResult` with the rendered HTML, title, and status.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout, Error as PlaywrightError


def _sanitize_html(text: str) -> str:
    """Strip lone UTF-16 surrogate characters that cause json.dump to crash.

    Playwright occasionally returns HTML containing lone surrogate code points
    (U+D800–U+DFFF) which are valid in Python's internal UCS-4 representation
    but illegal in UTF-8.  Passing such strings to ``json.dump(...,
    ensure_ascii=False)`` raises ``UnicodeEncodeError: surrogates not allowed``.
    We replace invalid surrogates with the Unicode replacement character (U+FFFD).
    """
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")

from app.resilience.retry import (
    BrowserError,
    NetworkError,
    PermanentError,
    TimeoutError,
    classify_playwright_error,
    with_retry,
)

logger = logging.getLogger(__name__)

# Default wait strategy – networkidle is too slow for most modern SPAs.
_WAIT_UNTIL = "domcontentloaded"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class PageResult:
    """The result of fetching a single URL."""

    url: str
    html: str = ""
    title: str = ""
    status_code: int | None = None
    success: bool = False
    error: str = ""
    fetched_via: str = "browser"  # "browser" | "httpx"


# ---------------------------------------------------------------------------
# Core fetch functions
# ---------------------------------------------------------------------------


@with_retry(max_attempts=2, min_wait=1.0, max_wait=3.0)
async def fetch_page_with_browser(
    page: Page,
    url: str,
    timeout_ms: int = 30_000,
) -> PageResult:
    """
    Navigate *url* using an existing Playwright page and return the rendered HTML.

    Parameters
    ----------
    page:
        An open Playwright Page object (caller owns lifecycle).
    url:
        The absolute URL to navigate to.
    timeout_ms:
        Navigation timeout in milliseconds.

    Returns
    -------
    PageResult
    """
    try:
        response = await page.goto(
            url,
            wait_until=_WAIT_UNTIL,
            timeout=timeout_ms,
        )

        # Give JS frameworks a moment to hydrate (bounded wait).
        try:
            await page.wait_for_load_state("networkidle", timeout=5_000)
        except PlaywrightTimeout:
            pass  # Acceptable – we already have the DOM content.

        status_code: int | None = response.status if response else None

        if status_code and status_code == 404:
            raise PermanentError(f"404 Not Found: {url}")
        if status_code and status_code >= 400:
            logger.warning("HTTP %s for %s", status_code, url)

        html = _sanitize_html(await page.content())
        title = await page.title()

        return PageResult(
            url=url,
            html=html,
            title=title,
            status_code=status_code,
            success=bool(html),
            fetched_via="browser",
        )

    except PermanentError:
        raise
    except PlaywrightTimeout as exc:
        raise TimeoutError(f"Timeout loading {url}: {exc}") from exc
    except PlaywrightError as exc:
        raise classify_playwright_error(exc) from exc


@with_retry(max_attempts=2, min_wait=1.0, max_wait=3.0)
async def fetch_page_with_httpx(
    url: str,
    timeout: int = 30,
    user_agent: str = "Mozilla/5.0",
) -> PageResult:
    """
    Fallback: fetch *url* using httpx (no JavaScript rendering).

    Only used when the browser layer fails completely.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        ) as client:
            response = await client.get(url)

        if response.status_code == 404:
            raise PermanentError(f"404 Not Found: {url}")

        return PageResult(
            url=url,
            html=_sanitize_html(response.text),
            title="",
            status_code=response.status_code,
            success=True,
            fetched_via="httpx",
        )

    except PermanentError:
        raise
    except httpx.TimeoutException as exc:
        raise TimeoutError(f"httpx timeout for {url}") from exc
    except httpx.ConnectError as exc:
        raise NetworkError(f"httpx connection error for {url}") from exc


async def fetch_page(
    page: Page,
    url: str,
    timeout_ms: int = 30_000,
    user_agent: str = "Mozilla/5.0",
    crawl_delay: float = 1.0,
) -> PageResult:
    """
    Attempt to fetch *url* via Playwright; fall back to httpx on failure.

    This is the main entry point for page fetching.  One page failure
    returns a failed :class:`PageResult` rather than raising, ensuring the
    pipeline continues.
    """
    if crawl_delay > 0:
        await asyncio.sleep(crawl_delay)

    # --- Attempt 1: Playwright ---
    try:
        result = await fetch_page_with_browser(page, url, timeout_ms)
        if result.success:
            return result
    except PermanentError as exc:
        return PageResult(url=url, success=False, error=str(exc))
    except (TimeoutError, NetworkError, BrowserError) as exc:
        logger.warning("Browser fetch failed for %s: %s. Trying httpx…", url, exc)

    # --- Attempt 2: httpx fallback ---
    try:
        result = await fetch_page_with_httpx(url, timeout=timeout_ms // 1000, user_agent=user_agent)
        return result
    except PermanentError as exc:
        return PageResult(url=url, success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        error_msg = f"Both browser and httpx failed for {url}: {exc}"
        logger.error(error_msg)
        return PageResult(url=url, success=False, error=error_msg)
