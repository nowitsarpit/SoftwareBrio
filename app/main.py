"""
Application entry point and CLI.

Supports two input modes:
  1. --domains postman.com supabase.com vapi.ai
  2. --input data/input.json

Output is configurable:
  --output data/output.json
  --output-format json   (default)
  --output-format csv

Run with:
  python -m app.main --input data/input.json
  python -m app.main --domains postman.com supabase.com vapi.ai
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from app.config import settings
from app.llm.extractor import LLMExtractor
from app.llm.search import build_search_provider
from app.models.company import CompanyEnrichment
from app.pipeline.enrichment import DomainEnrichmentPipeline
from app.pipeline.output import write_results
from app.utils.cache import PageCache
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lead-enrichment",
        description="Autonomous Lead Enrichment Agent – crawls company websites and extracts structured intelligence.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.main --domains postman.com supabase.com vapi.ai
  python -m app.main --input data/input.json
  python -m app.main --input data/input.json --output data/output.json --output-format json
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--domains",
        nargs="+",
        metavar="DOMAIN",
        help="One or more company domains to enrich.",
    )
    input_group.add_argument(
        "--input",
        metavar="FILE",
        type=Path,
        help='Path to a JSON file with {"domains": [...]}.',
    )

    parser.add_argument(
        "--output",
        metavar="FILE",
        type=Path,
        default=settings.default_output_path,
        help=f"Output file path (default: {settings.default_output_path}).",
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "csv"],
        default="json",
        dest="output_format",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=settings.log_level,
        dest="log_level",
        help=f"Log level (default: {settings.log_level}).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Disable the page cache for this run.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=settings.max_pages_per_domain,
        metavar="N",
        dest="max_pages",
        help=f"Max pages per domain (default: {settings.max_pages_per_domain}).",
    )

    return parser


def _load_domains(args: argparse.Namespace) -> list[str]:
    """Load the list of domains from CLI args or input file."""
    if args.domains:
        return args.domains

    input_path: Path = args.input
    if not input_path.exists():
        logger.error("Input file not found: %s", input_path)
        sys.exit(1)

    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", input_path, exc)
        sys.exit(1)

    if isinstance(data, list):
        domains = data
    elif isinstance(data, dict):
        domains = data.get("domains", [])
    else:
        domains = []

    if not domains:
        logger.error("No domains found in %s", input_path)
        sys.exit(1)

    return [str(d).strip() for d in domains if str(d).strip()]


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def run_enrichment(
    domains: list[str],
    output_path: Path,
    output_format: str,
    use_cache: bool,
    max_pages: int,
) -> list[CompanyEnrichment]:
    """
    Run the enrichment pipeline for all domains with bounded concurrency.

    Parameters
    ----------
    domains:
        List of raw domain inputs.
    output_path:
        Where to write the output file.
    output_format:
        "json" or "csv".
    use_cache:
        Whether to use the local page cache.
    max_pages:
        Max pages per domain (overrides settings).

    Returns
    -------
    list[CompanyEnrichment]
    """
    # Create a runtime copy of settings with CLI overrides applied.
    # We do NOT mutate the module-level singleton (important for test isolation).
    import copy
    runtime_settings = copy.copy(settings)
    runtime_settings.cache_enabled = use_cache
    runtime_settings.max_pages_per_domain = max_pages

    cache = PageCache(
        cache_dir=runtime_settings.cache_dir,
        ttl_hours=runtime_settings.cache_ttl_hours,
        enabled=runtime_settings.cache_enabled,
    )

    llm_extractor = LLMExtractor(
        api_key=runtime_settings.openai_api_key,
        model=runtime_settings.openai_model,
    )

    search_provider = build_search_provider(
        provider_name=runtime_settings.search_provider,
        api_key=runtime_settings.tavily_api_key,
    )

    pipeline = DomainEnrichmentPipeline(
        settings=runtime_settings,
        llm_extractor=llm_extractor,
        cache=cache,
        search_provider=search_provider,
    )

    semaphore = asyncio.Semaphore(runtime_settings.max_concurrent_domains)

    async def _enrich_with_semaphore(domain: str) -> CompanyEnrichment:
        async with semaphore:
            return await pipeline.run(domain)

    global_start = time.monotonic()

    tasks = [_enrich_with_semaphore(d) for d in domains]
    results: list[CompanyEnrichment] = await asyncio.gather(*tasks)

    total_duration = round(time.monotonic() - global_start, 2)

    # Write output.
    write_results(results, output_path, fmt=output_format)  # type: ignore[arg-type]

    # ---- Summary ----
    successful = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    total_pages = sum(r.crawl_metadata.pages_successful for r in results)
    total_tokens = sum(
        r.llm_usage.total_tokens or 0
        for r in results
        if r.llm_usage and r.llm_usage.total_tokens
    )
    total_cost = sum(
        r.llm_usage.estimated_cost_usd or 0.0
        for r in results
        if r.llm_usage and r.llm_usage.estimated_cost_usd
    )

    print("\n" + "=" * 60)
    print("  ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"  Processed:         {len(results)}")
    print(f"  Successful:        {successful}")
    print(f"  Partial:           {partial}")
    print(f"  Failed:            {failed}")
    print(f"  Total pages visited: {total_pages}")
    print(f"  Total duration:    {total_duration}s")
    if total_tokens:
        print(f"  Total tokens used: {total_tokens:,}")
    if total_cost:
        print(f"  Estimated cost:    ${total_cost:.4f} USD")
    print(f"  Output:            {output_path}")
    print("=" * 60 + "\n")

    return results


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    # Initialise logging before anything else.
    setup_logging(level=args.log_level, fmt=settings.log_format)

    domains = _load_domains(args)

    logger.info("Lead Enrichment Agent starting")
    logger.info("Model: %s | Max pages/domain: %d", settings.openai_model, args.max_pages)
    logger.info("Domains to process: %s", ", ".join(domains))

    asyncio.run(
        run_enrichment(
            domains=domains,
            output_path=args.output,
            output_format=args.output_format,
            use_cache=not args.no_cache,
            max_pages=args.max_pages,
        )
    )


if __name__ == "__main__":
    main()
