"""
Optional external search provider abstraction.

The pipeline works perfectly without any search provider (DisabledSearchProvider).
Enable TavilySearchProvider by setting:
    SEARCH_PROVIDER=tavily
    TAVILY_API_KEY=<key>

Search results are labelled as externally-sourced and never replace
crawled evidence – they only supplement it.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single result from an external search query."""

    url: str
    title: str
    content: str
    source: str = "external_search"


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Run a search query and return a list of results."""


class DisabledSearchProvider(SearchProvider):
    """
    No-op search provider.

    Used when SEARCH_PROVIDER=disabled (the default).
    Always returns an empty list without making any API calls.
    """

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        logger.debug("Search provider disabled – skipping query: %s", query)
        return []


class TavilySearchProvider(SearchProvider):
    """
    Tavily search provider for supplementary company intelligence.

    Requires:
        pip install tavily-python
        TAVILY_API_KEY=<key>
    """

    def __init__(self, api_key: str) -> None:
        try:
            from tavily import TavilyClient  # type: ignore[import]
            self._client = TavilyClient(api_key=api_key)
        except ImportError as exc:
            raise ImportError(
                "Install tavily-python to use TavilySearchProvider: "
                "pip install tavily-python"
            ) from exc

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Run a Tavily search and return structured results."""
        import asyncio

        loop = asyncio.get_event_loop()
        try:
            # Tavily client is sync – run in executor to avoid blocking the event loop.
            response = await loop.run_in_executor(
                None,
                lambda: self._client.search(query, max_results=max_results),
            )
            results: list[SearchResult] = []
            for item in response.get("results", []):
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        content=item.get("content", "")[:500],
                        source="tavily",
                    )
                )
            logger.debug("Tavily returned %d results for: %s", len(results), query)
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily search failed for '%s': %s", query, exc)
            return []


def build_search_provider(provider_name: str, api_key: str | None) -> SearchProvider:
    """
    Factory: construct the appropriate :class:`SearchProvider` from config.

    Parameters
    ----------
    provider_name:
        "disabled" or "tavily".
    api_key:
        API key (required for tavily, ignored for disabled).

    Returns
    -------
    SearchProvider
    """
    if provider_name == "tavily":
        if not api_key:
            logger.warning(
                "TAVILY_API_KEY not set – falling back to DisabledSearchProvider"
            )
            return DisabledSearchProvider()
        return TavilySearchProvider(api_key=api_key)

    return DisabledSearchProvider()
