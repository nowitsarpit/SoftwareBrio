"""
Output serialisation for enrichment results.

Supports JSON (mandatory) and CSV (optional).  Both formats produce
clean, human-readable files suitable for direct inspection or downstream
processing.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Literal

from app.models.company import CompanyEnrichment

logger = logging.getLogger(__name__)


def write_json(
    results: list[CompanyEnrichment],
    output_path: Path,
    indent: int = 2,
) -> None:
    """
    Write enrichment results to a JSON file.

    Parameters
    ----------
    results:
        List of enrichment records to write.
    output_path:
        Destination file path.
    indent:
        JSON indentation level.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = [r.model_dump(mode="json") for r in results]

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=indent, default=str)

    logger.info("JSON output written to %s (%d records)", output_path, len(results))


def write_csv(
    results: list[CompanyEnrichment],
    output_path: Path,
) -> None:
    """
    Write a flattened CSV summary of enrichment results.

    Complex nested fields (leadership, sources) are serialised as JSON
    strings within the CSV cells.

    Parameters
    ----------
    results:
        List of enrichment records.
    output_path:
        Destination .csv file path.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "domain",
        "status",
        "confidence_score",
        "company_overview",
        "ideal_customer_profile",
        "contact_emails",
        "leadership_count",
        "leadership",
        "pages_attempted",
        "pages_successful",
        "pages_failed",
        "duration_seconds",
        "llm_model",
        "total_tokens",
        "estimated_cost_usd",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for r in results:
            meta = r.crawl_metadata
            usage = r.llm_usage

            row = {
                "domain": r.domain,
                "status": r.status,
                "confidence_score": r.confidence_score,
                "company_overview": r.company_overview,
                "ideal_customer_profile": r.ideal_customer_profile,
                "contact_emails": "; ".join(r.contact_emails),
                "leadership_count": len(r.leadership),
                "leadership": json.dumps(
                    [m.model_dump(mode="json") for m in r.leadership],
                    ensure_ascii=False,
                ),
                "pages_attempted": meta.pages_attempted,
                "pages_successful": meta.pages_successful,
                "pages_failed": meta.pages_failed,
                "duration_seconds": meta.duration_seconds,
                "llm_model": usage.model if usage else "",
                "total_tokens": usage.total_tokens if usage else "",
                "estimated_cost_usd": usage.estimated_cost_usd if usage else "",
            }
            writer.writerow(row)

    logger.info("CSV output written to %s (%d records)", output_path, len(results))


def write_results(
    results: list[CompanyEnrichment],
    output_path: Path,
    fmt: Literal["json", "csv"] = "json",
) -> None:
    """
    Dispatch to the appropriate serialiser based on *fmt*.

    Parameters
    ----------
    results:
        Enrichment records to write.
    output_path:
        Destination file path.
    fmt:
        "json" or "csv".
    """
    if fmt == "csv":
        write_csv(results, output_path)
    else:
        write_json(results, output_path)
