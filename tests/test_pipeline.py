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
