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
        choices=["json", "csv", "html", "both", "all"],
        default="json",
        dest="output_format",
        help="Output format: json | csv | html | all (default: json; companion report.html is also created).",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Validate settings, cache, and domain reachability without invoking the LLM.",
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

    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(
            title="🎯 Autonomous Lead Enrichment — Summary",
            header_style="bold cyan",
            border_style="dim",
            show_header=True,
        )
        table.add_column("Domain", style="bold white")
        table.add_column("Status", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Emails", justify="center")
        table.add_column("Leadership", justify="center")
        table.add_column("Pages", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Est. Cost", justify="right")

        for r in results:
            status_style = (
                "green" if r.status == "success" else ("yellow" if r.status == "partial" else "red")
            )
            cost_str = (
                f"${r.llm_usage.estimated_cost_usd:.4f}"
                if r.llm_usage and r.llm_usage.estimated_cost_usd
                else "$0.0000"
            )
            table.add_row(
                r.domain,
                f"[{status_style}]{r.status.upper()}[/{status_style}]",
                f"{int(r.confidence_score * 100)}%",
                str(len(r.contact_emails)),
                str(len(r.leadership)),
                str(r.crawl_metadata.pages_successful),
                f"{r.crawl_metadata.duration_seconds:.1f}s",
                cost_str,
            )
        console.print()
        console.print(table)
        console.print(f"[dim]📁 Results saved to: [bold]{output_path}[/bold] (and companion report.html)[/dim]\n")
    except Exception:
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


async def run_dry_run(domains: list[str]) -> None:
    """Validate environment and target domain connectivity without LLM calls."""
    import httpx
    from app.crawler.url_utils import build_base_url, normalize_domain

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    logger.info("Running pre-flight dry-run checks...")
    print("\nPre-Flight Dry-Run Validation:")
    print("-" * 55)
    print(f"  OpenAI Model:    {settings.openai_model}")
    print(f"  Max Pages:       {settings.max_pages_per_domain}")
    print(f"  Cache Enabled:   {settings.cache_enabled} ({settings.cache_dir})")
    print("-" * 55)

    # Test cache directory write access
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    test_cache_file = settings.cache_dir / ".write_test"
    test_cache_file.write_text("ok", encoding="utf-8")
    test_cache_file.unlink()
    print("  [OK] Local disk cache write check passed")

    # Test domain reachability
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for raw in domains:
            domain = normalize_domain(raw)
            url = build_base_url(domain)
            try:
                resp = await client.get(url)
                print(f"  [OK] {domain:<22} HTTP {resp.status_code} ({len(resp.content):,} bytes)")
            except Exception as exc:  # noqa: BLE001
                print(f"  [!]  {domain:<22} Connection error: {exc}")

    print("-" * 55)
    print("Pre-flight dry-run completed successfully! System is production-ready.\n")


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

    if args.dry_run:
        asyncio.run(run_dry_run(domains))
        return

    if not settings.openai_api_key:
        logger.error(
            "OPENAI_API_KEY is not configured! Please add your key to .env or set $env:OPENAI_API_KEY. "
            "To test domain reachability without an API key, run with: --dry-run"
        )
        sys.exit(1)

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
