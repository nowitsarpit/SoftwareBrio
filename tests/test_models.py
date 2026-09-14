"""
Tests for Pydantic models: validation, field constraints, and serialisation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.company import (
    CompanyEnrichment,
    CrawlMetadata,
    LeadershipMember,
    LLMUsage,
    SourceEvidence,
)


class TestLeadershipMember:
    def test_valid_member(self) -> None:
        m = LeadershipMember(
            name="Jane Doe",
            title="CEO",
            linkedin_url="https://linkedin.com/in/janedoe",
            source_url="https://example.com/about",
        )
        assert m.name == "Jane Doe"
        assert m.linkedin_url == "https://linkedin.com/in/janedoe"

    def test_non_linkedin_url_coerced_to_none(self) -> None:
        m = LeadershipMember(
            name="John Smith",
            title="CTO",
            linkedin_url="https://twitter.com/johnsmith",
        )
        assert m.linkedin_url is None

    def test_empty_linkedin_url_is_none(self) -> None:
        m = LeadershipMember(name="Alice", title="VP", linkedin_url="")
        assert m.linkedin_url is None

    def test_null_linkedin_accepted(self) -> None:
        m = LeadershipMember(name="Bob", title="CFO", linkedin_url=None)
        assert m.linkedin_url is None


class TestSourceEvidence:
    def test_excerpt_truncated(self) -> None:
        long_excerpt = "x" * 500
        src = SourceEvidence(
            url="https://example.com",
            page_title="Test",
            relevant_excerpt=long_excerpt,
        )
        assert len(src.relevant_excerpt) == 300

    def test_defaults(self) -> None:
        src = SourceEvidence(url="https://example.com")
        assert src.page_title == ""
        assert src.relevant_excerpt == ""


class TestCrawlMetadata:
    def test_default_values(self) -> None:
        meta = CrawlMetadata()
        assert meta.pages_attempted == 0
        assert meta.pages_successful == 0
        assert meta.pages_failed == 0
        assert meta.duration_seconds == 0.0
        assert meta.errors == []

    def test_timestamp_set(self) -> None:
        meta = CrawlMetadata()
        assert meta.extraction_timestamp is not None


class TestLLMUsage:
    def test_total_tokens_computed(self) -> None:
        usage = LLMUsage(
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
        )
        assert usage.total_tokens == 150

    def test_null_usage(self) -> None:
        usage = LLMUsage()
        assert usage.input_tokens is None
        assert usage.total_tokens is None


class TestCompanyEnrichment:
    def test_confidence_clamped_above_one(self) -> None:
        e = CompanyEnrichment(domain="example.com", confidence_score=1.5)
        assert e.confidence_score == 1.0

    def test_confidence_clamped_below_zero(self) -> None:
        e = CompanyEnrichment(domain="example.com", confidence_score=-0.5)
        assert e.confidence_score == 0.0

    def test_emails_deduplicated(self) -> None:
        e = CompanyEnrichment(
            domain="example.com",
            contact_emails=["a@b.com", "A@B.COM", "c@d.com"],
        )
        assert e.contact_emails == ["a@b.com", "c@d.com"]

    def test_emails_normalised_lowercase(self) -> None:
        e = CompanyEnrichment(
            domain="example.com",
            contact_emails=["HELLO@EXAMPLE.COM"],
        )
        assert "hello@example.com" in e.contact_emails

    def test_default_status(self) -> None:
        e = CompanyEnrichment(domain="example.com")
        assert e.status == "success"

    def test_serialisation(self) -> None:
        e = CompanyEnrichment(
            domain="example.com",
            confidence_score=0.8,
            contact_emails=["hello@example.com"],
        )
        data = e.model_dump(mode="json")
        assert data["domain"] == "example.com"
        assert data["confidence_score"] == 0.8
        assert "hello@example.com" in data["contact_emails"]

    def test_requires_domain(self) -> None:
        with pytest.raises(ValidationError):
            CompanyEnrichment()  # type: ignore[call-arg]


class TestRawLLMExtraction:
    def test_valid_llm_payload(self) -> None:
        from app.llm.extractor import RawLLMExtraction

        payload = {
            "company_overview": "Acme builds tools. They serve developers.",
            "ideal_customer_profile": "Full-stack web developers and engineering leads.",
            "leadership": [
                {"name": "Alice", "title": "CEO", "linkedin_url": "https://linkedin.com/in/alice", "source_url": None}
            ],
            "confidence_score": 0.85,
            "sources": [
                {"url": "https://acme.com", "page_title": "Acme", "relevant_excerpt": "Acme is a toolmaker"}
            ],
        }
        obj = RawLLMExtraction.model_validate(payload)
        assert obj.company_overview.startswith("Acme builds tools")
        assert len(obj.leadership) == 1
        assert obj.leadership[0].name == "Alice"

    def test_missing_required_field_raises(self) -> None:
        from app.llm.extractor import RawLLMExtraction

        # Missing ideal_customer_profile
        payload = {
            "company_overview": "Acme builds tools. They serve developers.",
            "leadership": [],
            "confidence_score": 0.5,
            "sources": [],
        }
        with pytest.raises(ValidationError):
            RawLLMExtraction.model_validate(payload)
