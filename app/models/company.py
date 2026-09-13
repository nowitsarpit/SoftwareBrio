"""
Pydantic v2 data models for the lead enrichment pipeline.

All models use strict validation.  The schema is intentionally flat and
serialisation-friendly so that the same objects can be written to JSON,
CSV or a database without transformation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class LeadershipMember(BaseModel):
    """A single identified leadership / team member."""

    name: str = Field(..., description="Full name of the person")
    title: str = Field(..., description="Role or job title")
    linkedin_url: str | None = Field(
        None,
        description="LinkedIn profile URL found in the scraped evidence. "
        "Never fabricated.",
    )
    source_url: str | None = Field(
        None,
        description="The page URL where this person was discovered.",
    )

    @field_validator("linkedin_url", mode="before")
    @classmethod
    def validate_linkedin_url(cls, v: Any) -> str | None:
        """Accept only real linkedin.com URLs; coerce empty strings to None."""
        if not v:
            return None
        url = str(v).strip()
        if url and "linkedin.com" not in url.lower():
            return None
        return url or None


class SourceEvidence(BaseModel):
    """A crawled page that contributed to the enrichment result."""

    url: str = Field(..., description="Canonical URL of the source page")
    page_title: str = Field(default="", description="<title> of the page")
    relevant_excerpt: str = Field(
        default="",
        description="A short excerpt (≤300 chars) that supports the extraction.",
    )

    @field_validator("relevant_excerpt", mode="before")
    @classmethod
    def truncate_excerpt(cls, v: Any) -> str:
        if not v:
            return ""
        return str(v)[:300]


class CrawlMetadata(BaseModel):
    """Statistics about the crawl for a single domain."""

    pages_attempted: int = Field(default=0, ge=0)
    pages_successful: int = Field(default=0, ge=0)
    pages_failed: int = Field(default=0, ge=0)
    extraction_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_seconds: float = Field(default=0.0, ge=0.0)
    errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_counts(self) -> "CrawlMetadata":
        if self.pages_successful + self.pages_failed > self.pages_attempted:
            # Clamp rather than raise – partial data is still useful.
            self.pages_attempted = self.pages_successful + self.pages_failed
        return self


class LLMUsage(BaseModel):
    """Token and cost accounting for a single LLM call."""

    model: str = Field(default="")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _compute_total(self) -> "LLMUsage":
        if self.total_tokens is None and self.input_tokens and self.output_tokens:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self


# ---------------------------------------------------------------------------
# Root model
# ---------------------------------------------------------------------------


class CompanyEnrichment(BaseModel):
    """
    The fully enriched intelligence record for a single company domain.

    This is the root schema that the pipeline writes to the output file.
    Every field has a safe default so that partial results are always valid.
    """

    domain: str = Field(..., description="Normalised target domain (e.g. postman.com)")
    company_overview: str = Field(
        default="",
        description="Exactly two concise sentences describing the company, "
        "grounded in crawled evidence.",
    )
    ideal_customer_profile: str = Field(
        default="",
        description="Description of the ICP inferred from explicit website evidence.",
    )
    contact_emails: list[str] = Field(
        default_factory=list,
        description="Deduplicated, lowercased public contact emails.",
    )
    leadership: list[LeadershipMember] = Field(
        default_factory=list,
        description="Identified leadership / team members.",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Evidence-based confidence in the extracted intelligence.",
    )
    sources: list[SourceEvidence] = Field(
        default_factory=list,
        description="Crawled pages that contributed to this record.",
    )
    crawl_metadata: CrawlMetadata = Field(
        default_factory=CrawlMetadata,
        description="Statistics about the crawl.",
    )
    llm_usage: LLMUsage | None = Field(
        default=None,
        description="Token and cost accounting for the LLM call.",
    )
    pipeline_errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal errors encountered during enrichment.",
    )
    status: str = Field(
        default="success",
        description="Overall status: success | partial | failed",
    )

    @field_validator("contact_emails", mode="before")
    @classmethod
    def deduplicate_emails(cls, v: Any) -> list[str]:
        if not v:
            return []
        seen: set[str] = set()
        result: list[str] = []
        for email in v:
            normalised = str(email).strip().lower()
            if (
                normalised
                and "@" in normalised
                and "." in normalised.split("@")[-1]
                and normalised not in seen
            ):
                seen.add(normalised)
                result.append(normalised)
        return result


    @field_validator("confidence_score", mode="before")
    @classmethod
    def clamp_confidence(cls, v: Any) -> float:
        try:
            score = float(v)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))
