"""
Domain enrichment pipeline orchestrator.

This module owns the full enrichment workflow for a single domain:

  1. Normalise the domain.
  2. Open a Playwright page.
  3. Fetch the homepage (with cache check).
  4. Discover internal links.
  5. Score and rank candidate pages.
  6. Crawl the top-ranked pages (bounded).
  7. Extract clean text from each page.
  8. Extract emails deterministically.
  9. Build a compact evidence bundle.
 10. Call the LLM for structured extraction.
 11. Validate with Pydantic.
 12. Compute calibrated confidence.
 13. Return a :class:`CompanyEnrichment` result.

One domain failure NEVER propagates to other domains.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.browser.browser_manager import BrowserManager
from app.crawler.crawler import PageResult, fetch_page
from app.crawler.discovery import prioritize_links
from app.crawler.url_utils import build_base_url, normalize_domain
from app.extraction.contacts import extract_emails_from_html, merge_emails
from app.extraction.content import (
    deduplicate_content,
    extract_clean_text,
    get_page_title,
)
from app.extraction.links import extract_links_from_html
from app.llm.extractor import LLMExtractor
from app.llm.search import SearchProvider
from app.models.company import CompanyEnrichment, CrawlMetadata
from app.pipeline.confidence import compute_confidence
from app.resilience.retry import LLMError
from app.utils.cache import PageCache

if TYPE_CHECKING:
    from app.config import Settings
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------


@dataclass
class CrawledPage:
    """A successfully fetched and extracted page."""

    url: str
    title: str
    clean_text: str
    emails: list[str] = field(default_factory=list)
    raw_html: str = field(default="", repr=False)


# ---------------------------------------------------------------------------
# Evidence bundle builder
# ---------------------------------------------------------------------------


def _build_evidence_bundle(pages: list[CrawledPage], max_chars: int) -> str:
    """
    Build a compact, deduplicated evidence string from crawled pages.

    Parameters
    ----------
    pages:
        List of successfully crawled pages.
    max_chars:
        Maximum total characters to include.

    Returns
    -------
    str
        Compact evidence text ready for the LLM.
    """
    sections: list[str] = []
    for page in pages:
        header = f"--- PAGE: {page.url} ---\nTitle: {page.title}\n"
        sections.append(header + page.clean_text)

    combined = deduplicate_content(sections)

    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[evidence truncated to stay within token budget]"

    return combined


# ---------------------------------------------------------------------------
# Domain pipeline
# ---------------------------------------------------------------------------


class DomainEnrichmentPipeline:
    """
    Runs the full enrichment workflow for a single domain.

    Parameters
    ----------
    settings:
        Application configuration.
    llm_extractor:
        Shared LLM extractor instance.
    cache:
        Shared page cache.
    search_provider:
        Optional supplementary search provider.
    """

    def __init__(
        self,
        settings: "Settings",
        llm_extractor: LLMExtractor,
        cache: PageCache,
        search_provider: SearchProvider,
    ) -> None:
        self._settings = settings
        self._llm = llm_extractor
        self._cache = cache
        self._search = search_provider

    async def run(self, raw_domain: str) -> CompanyEnrichment:
        """
        Enrich a single domain.

        This method NEVER raises – all failures are captured as a
        partial/failed :class:`CompanyEnrichment` result.

        Parameters
        ----------
        raw_domain:
            Raw user-supplied domain (e.g. "https://www.postman.com/").

        Returns
        -------
        CompanyEnrichment
        """
        start_time = time.monotonic()
        domain = normalize_domain(raw_domain)
        base_url = build_base_url(domain)

        logger.info("=" * 60)
        logger.info("Starting enrichment for %s", domain)
        logger.info("=" * 60)

        crawl_meta = CrawlMetadata()
        pipeline_errors: list[str] = []
        crawled_pages: list[CrawledPage] = []

        try:
            async with BrowserManager(self._settings) as browser:
                page = await browser.new_page()
                try:
                    crawled_pages, crawl_meta, pipeline_errors = await self._crawl_domain(
                        page=page,
                        domain=domain,
                        base_url=base_url,
                    )
                finally:
                    await page.close()
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Browser layer failed for {domain}: {exc}"
            logger.error(error_msg)
            pipeline_errors.append(error_msg)
            crawl_meta.errors.append(error_msg)

        # Record duration.
        crawl_meta.duration_seconds = round(time.monotonic() - start_time, 2)

        # Determine overall status.
        if not crawled_pages:
            logger.error("[%s] No pages could be crawled", domain)
            return CompanyEnrichment(
                domain=domain,
                crawl_metadata=crawl_meta,
                pipeline_errors=pipeline_errors,
                status="failed",
            )

        # Collect deterministic emails from all crawled pages.
        all_emails = merge_emails([p.emails for p in crawled_pages])
        if all_emails:
            logger.info("[%s] Found %d public email(s)", domain, len(all_emails))

        # Build compact evidence bundle.
        evidence = _build_evidence_bundle(crawled_pages, self._settings.max_content_chars)
        logger.info(
            "[%s] Evidence bundle: %d chars from %d page(s)",
            domain,
            len(evidence),
            len(crawled_pages),
        )

        # LLM structured extraction.
        try:
            enrichment, _ = await self._llm.extract(
                domain=domain,
                evidence=evidence,
                crawl_metadata=crawl_meta,
                existing_emails=all_emails,
            )
        except LLMError as exc:
            error_msg = f"LLM extraction failed for {domain}: {exc}"
            logger.error(error_msg)
            pipeline_errors.append(error_msg)
            # Return partial result without LLM-extracted fields.
            enrichment = CompanyEnrichment(
                domain=domain,
                contact_emails=all_emails,
                crawl_metadata=crawl_meta,
                pipeline_errors=pipeline_errors,
                status="partial",
            )
            enrichment.confidence_score = compute_confidence(enrichment)
            return enrichment

        # Calibrate confidence.
        enrichment.confidence_score = compute_confidence(enrichment)
        enrichment.pipeline_errors = pipeline_errors
        enrichment.status = "success" if not pipeline_errors else "partial"

        duration = round(time.monotonic() - start_time, 2)
        logger.info(
            "[%s] Completed in %.1fs | confidence=%.2f | emails=%d | leaders=%d",
            domain,
            duration,
            enrichment.confidence_score,
            len(enrichment.contact_emails),
            len(enrichment.leadership),
        )
        return enrichment

    # ------------------------------------------------------------------
    # Private – crawl phase
    # ------------------------------------------------------------------

    async def _crawl_domain(
        self,
        page: "Page",
        domain: str,
        base_url: str,
    ) -> tuple[list[CrawledPage], CrawlMetadata, list[str]]:
        """
        Fetch the homepage, discover internal links, and crawl top-ranked pages.

        Returns
        -------
        tuple[list[CrawledPage], CrawlMetadata, list[str]]
            (crawled_pages, crawl_metadata, pipeline_errors)
        """
        meta = CrawlMetadata()
        errors: list[str] = []
        crawled: list[CrawledPage] = []
        visited_urls: set[str] = set()

        # ---- Step 1: Homepage ----
        homepage_result = await self._fetch_with_cache(page, base_url)
        meta.pages_attempted += 1

        if not homepage_result.success:
            error_msg = f"Homepage failed for {domain}: {homepage_result.error}"
            logger.error(error_msg)
            errors.append(error_msg)
            meta.pages_failed += 1
            meta.errors.append(error_msg)
            return crawled, meta, errors

        meta.pages_successful += 1
        visited_urls.add(homepage_result.url)
        homepage_page = self._process_page(homepage_result)
        crawled.append(homepage_page)
        logger.info("[%s] Homepage loaded (via %s)", domain, homepage_result.fetched_via)

        # ---- Step 2: Discover internal links ----
        raw_links = extract_links_from_html(homepage_result.html, base_url)
        candidate_pages = prioritize_links(
            raw_links=raw_links,
            base_url=base_url,
            target_domain=domain,
            max_pages=self._settings.max_pages_per_domain * 3,  # pre-filter generously
        )
        logger.info("[%s] Discovered %d internal links", domain, len(raw_links))
        logger.info(
            "[%s] Selected %d relevant candidate pages",
            domain,
            len(candidate_pages),
        )

        # ---- Step 3: Crawl top candidates ----
        remaining_budget = self._settings.max_pages_per_domain - 1  # -1 for homepage

        for candidate in candidate_pages:
            if remaining_budget <= 0:
                break
            if candidate.url in visited_urls:
                continue

            visited_urls.add(candidate.url)
            meta.pages_attempted += 1

            result = await self._fetch_with_cache(page, candidate.url)

            if result.success:
                meta.pages_successful += 1
                cp = self._process_page(result)
                crawled.append(cp)
                logger.info(
                    "[%s] Crawled: %s (score=%d)",
                    domain,
                    candidate.url,
                    candidate.score,
                )
                remaining_budget -= 1
            else:
                meta.pages_failed += 1
                error_msg = f"Failed: {candidate.url} – {result.error}"
                errors.append(error_msg)
                meta.errors.append(error_msg)
                logger.warning("[%s] %s", domain, error_msg)

        logger.info(
            "[%s] Crawl complete: %d successful, %d failed",
            domain,
            meta.pages_successful,
            meta.pages_failed,
        )
        return crawled, meta, errors

    # ------------------------------------------------------------------
    # Private – page processing
    # ------------------------------------------------------------------

    def _process_page(self, result: PageResult) -> CrawledPage:
        """Extract clean text and emails from a raw PageResult."""
        clean_text = extract_clean_text(
            result.html,
            max_chars=self._settings.max_content_chars // 3,
        )
        emails = extract_emails_from_html(result.html)
        title = result.title or get_page_title(result.html)

        return CrawledPage(
            url=result.url,
            title=title,
            clean_text=clean_text,
            emails=emails,
            raw_html=result.html,
        )

    async def _fetch_with_cache(self, page: "Page", url: str) -> PageResult:
        """Fetch a page, checking the cache first."""
        cached = self._cache.get(url)
        if cached:
            logger.debug("Cache hit: %s", url)
            return PageResult(
                url=url,
                html=cached.get("html", ""),
                title=cached.get("title", ""),
                status_code=cached.get("status_code"),
                success=True,
                fetched_via="cache",
            )

        result = await fetch_page(
            page=page,
            url=url,
            timeout_ms=self._settings.page_timeout * 1_000,
            user_agent=self._settings.user_agent,
            crawl_delay=self._settings.crawl_delay_seconds,
        )

        if result.success and self._settings.cache_enabled:
            self._cache.set(url, {
                "html": result.html,
                "title": result.title,
                "status_code": result.status_code,
            })

        return result
