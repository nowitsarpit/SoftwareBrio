"""
LLM-based structured information extraction.

Uses OpenAI's JSON mode / structured output to convert a pre-cleaned
evidence bundle into a validated :class:`CompanyEnrichment` record.

Key principles enforced here:
- Anti-hallucination: the prompt explicitly prohibits using pre-trained
  knowledge to fill gaps.
- Grounding: all extracted facts must come from the supplied evidence.
- Structured output: the LLM is asked for JSON matching our schema.
- Cost tracking: input/output tokens are recorded when available.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI, APIError, RateLimitError, APITimeoutError
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.models.company import (
    CompanyEnrichment,
    CrawlMetadata,
    LeadershipMember,
    LLMUsage,
    SourceEvidence,
)
from app.resilience.retry import LLMError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing table (informational only – NOT used for billing decisions)
# ---------------------------------------------------------------------------

# Prices in USD per 1 000 tokens, as of mid-2025.  Update as needed.
# Source: https://openai.com/pricing
_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":       {"input": 0.005,  "output": 0.015},
    "gpt-4o-mini":  {"input": 0.00015,"output": 0.0006},
    "gpt-4-turbo":  {"input": 0.01,   "output": 0.03},
    "gpt-3.5-turbo":{"input": 0.0005, "output": 0.0015},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Estimate API cost in USD.  Returns None if model pricing is unknown."""
    for key, prices in _MODEL_PRICING.items():
        if model.startswith(key):
            cost = (
                input_tokens / 1_000 * prices["input"]
                + output_tokens / 1_000 * prices["output"]
            )
            return round(cost, 6)
    return None


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a company intelligence extraction assistant.

Your ONLY source of information is the website evidence provided in the user message.
You MUST NOT use your pre-trained knowledge to fill in any missing information.
If a field is not supported by the evidence, return null or an empty array — do not invent data.

Rules:
1. company_overview: Exactly two concise sentences describing what the company does and who it serves, based ONLY on the evidence.
2. ideal_customer_profile: Describe the likely target customer based on EXPLICIT evidence (pricing tiers, customer logos, use-case copy, etc.). Do not guess.
3. contact_emails: Leave EMPTY — emails are extracted deterministically before this call.
4. leadership: Include ONLY people explicitly named with a role on the website. For linkedin_url, include ONLY URLs that appear verbatim in the evidence. Return null for missing LinkedIn URLs.
5. confidence_score: A float 0.0–1.0 reflecting evidence quality. Be conservative.
6. sources: List the most relevant source URLs from the evidence that support your extraction.

Return ONLY a valid JSON object matching this schema:
{
  "company_overview": "string (two sentences)",
  "ideal_customer_profile": "string",
  "leadership": [
    {"name": "string", "title": "string", "linkedin_url": "string|null", "source_url": "string|null"}
  ],
  "confidence_score": 0.0,
  "sources": [
    {"url": "string", "page_title": "string", "relevant_excerpt": "string (max 200 chars)"}
  ]
}
"""


def _build_user_prompt(domain: str, evidence: str) -> str:
    """Build the user turn of the extraction prompt."""
    return f"""\
Domain: {domain}

=== WEBSITE EVIDENCE (extracted from {domain}) ===

{evidence}

=== END OF EVIDENCE ===

Extract the company intelligence described in the system prompt.
Remember: use ONLY the evidence above. Do not use pre-trained knowledge.
"""


# ---------------------------------------------------------------------------
# Retry decorator for OpenAI calls
# ---------------------------------------------------------------------------

_openai_retry = retry(
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, LLMError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Extractor class
# ---------------------------------------------------------------------------


class RawLLMExtraction(BaseModel):
    """Strict schema for raw LLM extraction payload."""

    company_overview: str = Field(
        ...,
        description="Exactly two concise sentences describing what the company does and who it serves.",
    )
    ideal_customer_profile: str = Field(
        ...,
        description="Description of the ideal customer profile grounded in explicit evidence.",
    )
    leadership: list[LeadershipMember] = Field(
        default_factory=list,
        description="Identified leadership / key team members.",
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Initial confidence score in [0.0, 1.0].",
    )
    sources: list[SourceEvidence] = Field(
        default_factory=list,
        description="Source URLs that support this extraction.",
    )


# Strict JSON Schema for OpenAI Structured Outputs
_STRUCTURED_JSON_SCHEMA: dict[str, Any] = {
    "name": "company_intelligence_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "company_overview": {
                "type": "string",
                "description": "Exactly two concise sentences describing what the company does and who it serves.",
            },
            "ideal_customer_profile": {
                "type": "string",
                "description": "Description of the ideal customer profile based on evidence.",
            },
            "leadership": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "title": {"type": "string"},
                        "linkedin_url": {"type": ["string", "null"]},
                        "source_url": {"type": ["string", "null"]},
                    },
                    "required": ["name", "title", "linkedin_url", "source_url"],
                    "additionalProperties": False,
                },
            },
            "confidence_score": {
                "type": "number",
                "description": "Float confidence score between 0.0 and 1.0.",
            },
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "page_title": {"type": "string"},
                        "relevant_excerpt": {"type": "string"},
                    },
                    "required": ["url", "page_title", "relevant_excerpt"],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "company_overview",
            "ideal_customer_profile",
            "leadership",
            "confidence_score",
            "sources",
        ],
        "additionalProperties": False,
    },
}


class LLMExtractor:
    """
    Wraps the OpenAI client for structured company-intelligence extraction.

    Uses OpenAI Structured Outputs (JSON Schema) backed by Pydantic validation
    and an automated self-repair loop for schema self-correction.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model

    async def extract(
        self,
        domain: str,
        evidence: str,
        crawl_metadata: CrawlMetadata,
        existing_emails: list[str],
    ) -> tuple[CompanyEnrichment, LLMUsage | None]:
        """
        Run the LLM extraction for a single domain with schema validation and self-repair.

        Parameters
        ----------
        domain:
            Normalised target domain.
        evidence:
            Pre-cleaned, deduplicated text from the crawled pages.
        crawl_metadata:
            Statistics from the crawl phase (attached to the result).
        existing_emails:
            Deterministically extracted emails (merged into the result).

        Returns
        -------
        tuple[CompanyEnrichment, LLMUsage | None]
        """
        user_prompt = _build_user_prompt(domain, evidence)
        logger.info("[%s] Sending evidence to LLM (%d chars)", domain, len(evidence))

        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        total_input_tok = 0
        total_output_tok = 0
        max_repairs = 2
        last_error = ""
        validated_payload: RawLLMExtraction | None = None

        for attempt in range(max_repairs + 1):
            try:
                raw_json, usage = await self._call_openai(messages)
                if usage:
                    total_input_tok += usage.input_tokens or 0
                    total_output_tok += usage.output_tokens or 0

                validated_payload = RawLLMExtraction.model_validate(raw_json)
                break  # Schema validation succeeded
            except (RateLimitError, APITimeoutError, APIError) as exc:
                raise LLMError(f"OpenAI API error for {domain}: {exc}") from exc
            except Exception as parse_exc:  # noqa: BLE001
                last_error = str(parse_exc)
                logger.warning(
                    "[%s] Schema validation attempt %d failed: %s. Initiating self-repair...",
                    domain,
                    attempt + 1,
                    last_error,
                )
                if attempt < max_repairs:
                    repair_prompt = (
                        f"The previous output was invalid according to our schema.\n"
                        f"Validation Error: {last_error}\n"
                        f"Please re-extract and return ONLY valid JSON matching the exact schema."
                    )
                    messages.append({"role": "user", "content": repair_prompt})

        # Aggregated usage
        aggregated_usage = LLMUsage(
            model=self._model,
            input_tokens=total_input_tok,
            output_tokens=total_output_tok,
            total_tokens=total_input_tok + total_output_tok,
            estimated_cost_usd=_estimate_cost(self._model, total_input_tok, total_output_tok),
        )

        if not validated_payload:
            raise LLMError(f"Extraction failed schema validation after self-repair for {domain}: {last_error}")

        enrichment = CompanyEnrichment(
            domain=domain,
            company_overview=validated_payload.company_overview,
            ideal_customer_profile=validated_payload.ideal_customer_profile,
            contact_emails=existing_emails,  # deterministic source
            leadership=validated_payload.leadership,
            confidence_score=validated_payload.confidence_score,
            sources=validated_payload.sources,
            crawl_metadata=crawl_metadata,
            llm_usage=aggregated_usage,
            status="success",
        )

        logger.info(
            "[%s] Structured extraction successful (confidence=%.2f, leaders=%d)",
            domain,
            enrichment.confidence_score,
            len(enrichment.leadership),
        )
        return enrichment, aggregated_usage

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @_openai_retry
    async def _call_openai(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[dict[str, Any], LLMUsage | None]:
        """Call the OpenAI endpoint using Structured Outputs with JSON schema."""
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_schema", "json_schema": _STRUCTURED_JSON_SCHEMA},
                temperature=0.1,
            )
        except Exception as exc:  # Fallback for models without strict json_schema support
            logger.debug("Structured output json_schema call failed (%s); falling back to json_object", exc)
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                temperature=0.1,
            )

        content = response.choices[0].message.content or "{}"

        usage: LLMUsage | None = None
        if response.usage:
            input_tok = response.usage.prompt_tokens
            output_tok = response.usage.completion_tokens
            usage = LLMUsage(
                model=self._model,
                input_tokens=input_tok,
                output_tokens=output_tok,
                total_tokens=response.usage.total_tokens,
                estimated_cost_usd=_estimate_cost(self._model, input_tok, output_tok),
            )

        return json.loads(content), usage
