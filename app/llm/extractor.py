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


class LLMExtractor:
    """
    Wraps the OpenAI client for structured company-intelligence extraction.

    Parameters
    ----------
    api_key:
        OpenAI API key (never logged).
    model:
        The OpenAI model to use.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def extract(
        self,
        domain: str,
        evidence: str,
        crawl_metadata: CrawlMetadata,
        existing_emails: list[str],
    ) -> tuple[CompanyEnrichment, LLMUsage | None]:
        """
        Run the LLM extraction for a single domain.

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

        try:
            raw_json, usage = await self._call_openai(user_prompt)
        except (RateLimitError, APITimeoutError, APIError) as exc:
            raise LLMError(f"OpenAI API error for {domain}: {exc}") from exc

        parsed = self._parse_response(raw_json, domain)

        enrichment = CompanyEnrichment(
            domain=domain,
            company_overview=parsed.get("company_overview", ""),
            ideal_customer_profile=parsed.get("ideal_customer_profile", ""),
            contact_emails=existing_emails,  # deterministic source
            leadership=self._parse_leadership(parsed.get("leadership", []), domain),
            confidence_score=float(parsed.get("confidence_score", 0.0)),
            sources=self._parse_sources(parsed.get("sources", [])),
            crawl_metadata=crawl_metadata,
            llm_usage=usage,
            status="success",
        )

        logger.info(
            "[%s] Structured extraction successful (confidence=%.2f)",
            domain,
            enrichment.confidence_score,
        )
        return enrichment, usage

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @_openai_retry
    async def _call_openai(self, user_prompt: str) -> tuple[dict[str, Any], LLMUsage | None]:
        """Call the OpenAI chat completion endpoint and return (parsed_dict, usage)."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for deterministic, factual output.
        )

        content = response.choices[0].message.content or "{}"

        # Build usage record.
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
            logger.debug(
                "LLM usage: %d input + %d output = %d total tokens",
                input_tok,
                output_tok,
                response.usage.total_tokens,
            )

        return json.loads(content), usage

    @staticmethod
    def _parse_response(raw: dict[str, Any], domain: str) -> dict[str, Any]:
        """Validate and sanitise the raw LLM JSON dict."""
        if not isinstance(raw, dict):
            logger.warning("[%s] LLM returned non-dict response", domain)
            return {}
        return raw

    @staticmethod
    def _parse_leadership(raw: list[Any], domain: str) -> list[LeadershipMember]:
        """Parse and validate leadership entries from the LLM response."""
        members: list[LeadershipMember] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                member = LeadershipMember(
                    name=str(item.get("name", "")).strip(),
                    title=str(item.get("title", "")).strip(),
                    linkedin_url=item.get("linkedin_url"),
                    source_url=item.get("source_url"),
                )
                if member.name:
                    members.append(member)
            except Exception as exc:  # noqa: BLE001
                logger.debug("[%s] Could not parse leadership entry %s: %s", domain, item, exc)
        return members

    @staticmethod
    def _parse_sources(raw: list[Any]) -> list[SourceEvidence]:
        """Parse and validate source evidence entries from the LLM response."""
        sources: list[SourceEvidence] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                src = SourceEvidence(
                    url=str(item.get("url", "")).strip(),
                    page_title=str(item.get("page_title", "")).strip(),
                    relevant_excerpt=str(item.get("relevant_excerpt", "")).strip(),
                )
                if src.url:
                    sources.append(src)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not parse source entry %s: %s", item, exc)
        return sources
