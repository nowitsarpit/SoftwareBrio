"""
Deterministic confidence scoring for enrichment results.

The LLM outputs an initial confidence score, but we cap/adjust it based on
objective signals from the crawl so that confidence cannot be falsely inflated
by a verbose-but-empty LLM response.

Scoring bands:
  0.9 – 1.0:  Strong multi-page evidence; most fields populated.
  0.7 – 0.89: Good evidence; some fields missing.
  0.4 – 0.69: Partial evidence; significant gaps.
  0.0 – 0.39: Poor crawl; little usable information.
"""

from __future__ import annotations

from app.models.company import CompanyEnrichment


def compute_confidence(enrichment: CompanyEnrichment) -> float:
    """
    Return a calibrated confidence score in [0.0, 1.0].

    Combines deterministic completeness signals with the LLM's self-assessed
    score.  Neither source alone is authoritative.

    Parameters
    ----------
    enrichment:
        The partially-populated enrichment record (confidence_score may be
        the raw LLM value at this point).

    Returns
    -------
    float
        Adjusted confidence in [0.0, 1.0].
    """
    meta = enrichment.crawl_metadata
    score = 0.0

    # --- Signal 1: Homepage successfully retrieved ---
    if meta.pages_successful > 0:
        score += 0.20

    # --- Signal 2: Number of relevant pages crawled ---
    if meta.pages_successful >= 3:
        score += 0.15
    elif meta.pages_successful >= 2:
        score += 0.10
    elif meta.pages_successful >= 1:
        score += 0.05

    # --- Signal 3: Company overview populated ---
    if enrichment.company_overview and len(enrichment.company_overview) > 50:
        score += 0.20

    # --- Signal 4: ICP populated ---
    if enrichment.ideal_customer_profile and len(enrichment.ideal_customer_profile) > 30:
        score += 0.15

    # --- Signal 5: Contact emails found ---
    if enrichment.contact_emails:
        score += 0.10

    # --- Signal 6: Leadership found ---
    if enrichment.leadership:
        score += 0.10
        if len(enrichment.leadership) >= 3:
            score += 0.05

    # --- Signal 7: Multiple source pages ---
    if len(enrichment.sources) >= 3:
        score += 0.05

    # --- Penalty: Crawl failures ---
    if meta.pages_failed > 0 and meta.pages_attempted > 0:
        failure_rate = meta.pages_failed / meta.pages_attempted
        score -= failure_rate * 0.15

    # --- Blend with LLM self-assessment (small weight) ---
    llm_score = float(enrichment.confidence_score or 0.0)
    blended = 0.80 * score + 0.20 * llm_score

    # Clamp to [0, 1].
    return round(max(0.0, min(1.0, blended)), 3)
