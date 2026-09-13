"""
Playwright browser manager.

Provides an async context manager that owns the entire Playwright lifecycle
(playwright → browser → context → page) and ensures clean shutdown even
on errors.  One BrowserManager instance is shared across all pages for a
single domain crawl to minimise browser process overhead.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import TYPE_CHECKING

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    Route,
    async_playwright,
)

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)

# Resources to block – saves bandwidth and speeds up page loads.
# We do NOT block images/fonts that are needed for rendering; we only block
# clearly non-content resources.
_BLOCKED_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "media",      # video / audio
        "websocket",  # not needed for static extraction
        "eventsource",
        "manifest",
        "other",
    }
)

# Known tracking/analytics URL patterns to block.
_BLOCKED_URL_PATTERNS: tuple[str, ...] = (
    "google-analytics.com",
    "googletagmanager.com",
    "doubleclick.net",
    "facebook.com/tr",
    "hotjar.com",
    "intercom.io",
    "segment.io",
    "segment.com",
    "mixpanel.com",
    "amplitude.com",
    "heap.io",
    "fullstory.com",
    "clarity.ms",
    "sentry.io",
)


async def _route_handler(route: Route) -> None:
    """Selectively block non-essential resources."""
    request = route.request
    resource_type = request.resource_type

    if resource_type in _BLOCKED_RESOURCE_TYPES:
        await route.abort()
        return

    url = request.url.lower()
    for pattern in _BLOCKED_URL_PATTERNS:
        if pattern in url:
            await route.abort()
            return

    await route.continue_()


class BrowserManager:
    """
    Async context manager that owns a single Playwright Chromium process.

    Usage
    -----
    ::

        async with BrowserManager(settings) as manager:
            page = await manager.new_page()
            await page.goto("https://example.com")
            await page.close()
    """

    def __init__(self, settings: "Settings") -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "BrowserManager":
        await self._launch()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._shutdown()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def new_page(self) -> Page:
        """
        Create a new isolated page within the shared browser context.

        The caller is responsible for closing the page after use.
        """
        if self._context is None:
            raise RuntimeError("BrowserManager is not active – use 'async with'")
        page = await self._context.new_page()
        page.set_default_navigation_timeout(self._settings.page_timeout * 1_000)
        page.set_default_timeout(self._settings.page_timeout * 1_000)
        return page

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _launch(self) -> None:
        """Launch Chromium and create a shared browser context."""
        logger.debug("Launching Playwright Chromium (headless=%s)", self._settings.headless)
        pw = await async_playwright().start()
        self._playwright = pw

        self._browser = await pw.chromium.launch(
            headless=self._settings.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self._context = await self._browser.new_context(
            user_agent=self._settings.user_agent,
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
            java_script_enabled=True,
            accept_downloads=False,
        )

        # Block non-essential resources globally on this context.
        await self._context.route("**/*", _route_handler)
        logger.debug("Browser context ready")

    async def _shutdown(self) -> None:
        """Gracefully close context → browser → playwright."""
        try:
            if self._context:
                await self._context.close()
        except PlaywrightError as exc:
            logger.debug("Context close error (ignored): %s", exc)

        try:
            if self._browser:
                await self._browser.close()
        except PlaywrightError as exc:
            logger.debug("Browser close error (ignored): %s", exc)

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Playwright stop error (ignored): %s", exc)

        self._context = None
        self._browser = None
        self._playwright = None
        logger.debug("Browser shut down cleanly")
