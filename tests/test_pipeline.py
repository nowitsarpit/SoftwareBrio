"""
Pipeline-level tests using mocks.

These tests verify the pipeline's failure-handling, partial-result, and
orchestration logic without making any real network or LLM calls.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.company import CompanyEnrichment, CrawlMetadata, LLMUsage
from app.pipeline.confidence import compute_confidence


class TestComputeConfidence:
    """Deterministic confidence scoring tests."""

    def _make_enrichment(self, **kwargs: object) -> CompanyEnrichment:
        return CompanyEnrichment(domain="example.com", **kwargs)  # type: ignore[arg-type]

    def test_no_pages_yields_low_confidence(self) -> None:
        e = self._make_enrichment(
            crawl_metadata=CrawlMetadata(pages_attempted=0, pages_successful=0),
        )
        score = compute_confidence(e)
        assert score < 0.3

    def test_full_evidence_yields_high_confidence(self) -> None:
        from app.models.company import LeadershipMember, SourceEvidence

        e = self._make_enrichment(
            company_overview="Two sentence overview about the company and its products.",
            ideal_customer_profile="Enterprise software teams seeking automation solutions.",
            contact_emails=["hello@example.com"],
            leadership=[
                LeadershipMember(name="Jane Doe", title="CEO"),
                LeadershipMember(name="John Smith", title="CTO"),
                LeadershipMember(name="Alice Lee", title="CFO"),
            ],
            sources=[
                SourceEvidence(url="https://example.com/about"),
                SourceEvidence(url="https://example.com/team"),
                SourceEvidence(url="https://example.com/pricing"),
            ],
            crawl_metadata=CrawlMetadata(
                pages_attempted=5,
                pages_successful=5,
                pages_failed=0,
            ),
            confidence_score=0.9,
        )
        score = compute_confidence(e)
        assert score >= 0.7

    def test_score_always_clamped(self) -> None:
        e = self._make_enrichment(confidence_score=1.5)
        e.crawl_metadata = CrawlMetadata(pages_successful=10)
        score = compute_confidence(e)
        assert 0.0 <= score <= 1.0

    def test_failures_reduce_confidence(self) -> None:
        meta_good = CrawlMetadata(pages_attempted=5, pages_successful=5, pages_failed=0)
        meta_bad = CrawlMetadata(pages_attempted=5, pages_successful=2, pages_failed=3)

        e_good = self._make_enrichment(
            company_overview="Good overview of the company.",
            crawl_metadata=meta_good,
        )
        e_bad = self._make_enrichment(
            company_overview="Good overview of the company.",
            crawl_metadata=meta_bad,
        )
        assert compute_confidence(e_good) > compute_confidence(e_bad)


class TestPartialResults:
    """Verify that partial results are always valid CompanyEnrichment objects."""

    def test_failed_domain_returns_valid_schema(self) -> None:
        result = CompanyEnrichment(
            domain="unreachable.com",
            status="failed",
            crawl_metadata=CrawlMetadata(
                pages_attempted=1,
                pages_successful=0,
                pages_failed=1,
                errors=["DNS resolution failed"],
            ),
        )
        data = result.model_dump(mode="json")
        assert data["domain"] == "unreachable.com"
        assert data["status"] == "failed"
        assert data["contact_emails"] == []
        assert data["leadership"] == []
        assert 0.0 <= data["confidence_score"] <= 1.0

    def test_partial_result_is_serialisable(self) -> None:
        import json

        result = CompanyEnrichment(
            domain="partial.com",
            company_overview="Some overview.",
            contact_emails=["info@partial.com"],
            status="partial",
            crawl_metadata=CrawlMetadata(pages_successful=1, pages_failed=2),
        )
        dumped = result.model_dump(mode="json")
        # Must round-trip through JSON without error.
        json_str = json.dumps(dumped)
        reloaded = json.loads(json_str)
        assert reloaded["domain"] == "partial.com"


class TestPipelineEnhancements:
    """Tests for search integration, multi-hop discovery, and budget accounting."""

    @pytest.mark.asyncio
    async def test_search_integration_supplements_evidence(self) -> None:
        from app.config import settings
        from app.llm.extractor import LLMExtractor
        from app.llm.search import SearchProvider, SearchResult
        from app.pipeline.enrichment import DomainEnrichmentPipeline
        from app.utils.cache import PageCache

        class MockSearch(SearchProvider):
            async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
                return [
                    SearchResult(
                        url="https://linkedin.com/in/founder",
                        title="Jane Doe - Founder Profile",
                        content="Jane Doe is CEO of example.com",
                    )
                ]

        mock_llm = MagicMock(spec=LLMExtractor)
        mock_llm.extract = AsyncMock(
            return_value=(
                CompanyEnrichment(
                    domain="example.com",
                    company_overview="Example Corp builds software.",
                    confidence_score=0.9,
                ),
                LLMUsage(model="gpt-4o-mini", total_tokens=100),
            )
        )

        test_settings = settings.model_copy()
        test_settings.search_provider = "tavily"
        cache = PageCache(cache_dir=test_settings.cache_dir, enabled=False)

        pipeline = DomainEnrichmentPipeline(
            settings=test_settings,
            llm_extractor=mock_llm,
            cache=cache,
            search_provider=MockSearch(),
        )

        # Mock crawling so it returns 1 page
        with patch.object(
            pipeline,
            "_crawl_domain",
            AsyncMock(
                return_value=(
                    [
                        MagicMock(
                            url="https://example.com/",
                            title="Home",
                            clean_text="Clean body text about widgets.",
                            emails=["contact@example.com"],
                        )
                    ],
                    CrawlMetadata(pages_attempted=1, pages_successful=1),
                    [],
                )
            ),
        ):
            res = await pipeline.run("example.com")
            assert res.domain == "example.com"
            assert mock_llm.extract.called
            evidence_sent = mock_llm.extract.call_args[1]["evidence"]
            assert "SUPPLEMENTARY EXTERNAL SEARCH EVIDENCE" in evidence_sent
            assert "Jane Doe" in evidence_sent

    @pytest.mark.asyncio
    async def test_crawler_retries_on_transient_error(self) -> None:
        from app.crawler.crawler import fetch_page_with_browser
        from app.resilience.retry import NetworkError

        mock_page = MagicMock()
        attempts = 0

        async def faulty_goto(*args: object, **kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise NetworkError("DNS temporary glitch")
            mock_page.status = 200

        mock_page.goto = AsyncMock(side_effect=faulty_goto)
        mock_page.content = AsyncMock(return_value="<html><body>Content</body></html>")
        mock_page.title = AsyncMock(return_value="Success Title")
        mock_page.wait_for_load_state = AsyncMock()

        result = await fetch_page_with_browser(mock_page, "https://example.com")
        assert attempts == 2
        assert result.success is True
        assert result.title == "Success Title"

    @pytest.mark.asyncio
    async def test_budget_decremented_on_failed_candidate_page(self) -> None:
        from app.config import settings
        from app.crawler.crawler import PageResult
        from app.llm.extractor import LLMExtractor
        from app.llm.search import DisabledSearchProvider
        from app.pipeline.enrichment import DomainEnrichmentPipeline
        from app.utils.cache import PageCache

        test_settings = settings.model_copy()
        test_settings.max_pages_per_domain = 3
        cache = PageCache(cache_dir=test_settings.cache_dir, enabled=False)

        mock_llm = MagicMock(spec=LLMExtractor)
        mock_llm.extract = AsyncMock(
            return_value=(
                CompanyEnrichment(domain="budget-test.com", confidence_score=0.7),
                None,
            )
        )

        pipeline = DomainEnrichmentPipeline(
            settings=test_settings,
            llm_extractor=mock_llm,
            cache=cache,
            search_provider=DisabledSearchProvider(),
        )

        # Mock _fetch_with_cache:
        # 1. Homepage returns HTML with 5 candidate links
        # 2. Candidate 1 fails (success=False)
        # 3. Candidate 2 succeeds
        # 4. Candidate 3, 4, 5 must NOT be attempted because budget (3 pages) is exhausted
        async def mock_fetch(page: object, url: str) -> PageResult:
            if url == "https://budget-test.com/":
                return PageResult(
                    url=url,
                    html="""
                    <html><body>
                        <a href="/page1">Page 1</a>
                        <a href="/page2">Page 2</a>
                        <a href="/page3">Page 3</a>
                        <a href="/page4">Page 4</a>
                    </body></html>
                    """,
                    status_code=200,
                    success=True,
                )
            if "page1" in url:
                # Failed candidate
                return PageResult(
                    url=url,
                    html="",
                    status_code=500,
                    success=False,
                    error="Server error 500",
                )
            return PageResult(
                url=url,
                html="<html><body>Clean content</body></html>",
                status_code=200,
                success=True,
            )

        with patch.object(pipeline, "_fetch_with_cache", side_effect=mock_fetch):
            mock_page = MagicMock()
            crawled, meta, errors = await pipeline._crawl_domain(
                mock_page, "budget-test.com", "https://budget-test.com/"
            )

            # Exactly 3 pages attempted (home + page1 + page2), page3 never attempted
            assert meta.pages_attempted == 3
            assert meta.pages_successful == 2
            assert meta.pages_failed == 1
            assert len(crawled) == 2

    @pytest.mark.asyncio
    async def test_multi_hop_discovery_queues_subpages(self) -> None:
        from app.config import settings
        from app.crawler.crawler import PageResult
        from app.llm.extractor import LLMExtractor
        from app.llm.search import DisabledSearchProvider
        from app.pipeline.enrichment import DomainEnrichmentPipeline
        from app.utils.cache import PageCache

        test_settings = settings.model_copy()
        test_settings.max_pages_per_domain = 3
        cache = PageCache(cache_dir=test_settings.cache_dir, enabled=False)

        mock_llm = MagicMock(spec=LLMExtractor)
        pipeline = DomainEnrichmentPipeline(
            settings=test_settings,
            llm_extractor=mock_llm,
            cache=cache,
            search_provider=DisabledSearchProvider(),
        )

        # Homepage links only to /about
        # /about page contains link to /about/leadership
        visited_urls_order: list[str] = []

        async def mock_fetch(page: object, url: str) -> PageResult:
            visited_urls_order.append(url)
            if url == "https://multihop-test.com/":
                return PageResult(
                    url=url,
                    html='<html><body><a href="/about">About Us</a></body></html>',
                    status_code=200,
                    success=True,
                )
            if "/about" in url and "/leadership" not in url:
                return PageResult(
                    url=url,
                    html='<html><body><a href="/about/leadership">Meet our leadership</a></body></html>',
                    status_code=200,
                    success=True,
                )
            return PageResult(
                url=url,
                html="<html><body>Leadership: Jane Doe, Founder & CEO</body></html>",
                status_code=200,
                success=True,
            )

        with patch.object(pipeline, "_fetch_with_cache", side_effect=mock_fetch):
            mock_page = MagicMock()
            crawled, meta, errors = await pipeline._crawl_domain(
                mock_page, "multihop-test.com", "https://multihop-test.com/"
            )

            assert len(crawled) == 3
            urls = [p.url for p in crawled]
            assert "https://multihop-test.com/about" in urls
            assert "https://multihop-test.com/about/leadership" in urls

