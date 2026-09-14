"""
Central configuration system using pydantic-settings.

All configuration is read from environment variables (and .env file via
python-dotenv).  Never hardcode secrets or company-specific values here.

Usage
-----
    from app.config import settings
    print(settings.openai_model)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings loaded from environment variables / .env file.
    All fields are typed and have safe defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (read from .env or OPENAI_API_KEY environment variable)",
    )
    openai_base_url: str | None = Field(
        default=None,
        description="Custom base URL for OpenAI-compatible providers (Groq, OpenRouter, Gemini, etc.)",
    )

    # ------------------------------------------------------------------ #
    # OpenAI
    # ------------------------------------------------------------------ #
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use for extraction",
    )
    openai_max_retries: int = Field(
        default=3,
        description="Max retry attempts for OpenAI API calls",
    )

    # ------------------------------------------------------------------ #
    # Crawling
    # ------------------------------------------------------------------ #
    max_pages_per_domain: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Maximum pages to crawl per domain",
    )
    max_concurrent_domains: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Concurrent domain-enrichment tasks",
    )
    request_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="HTTP request timeout in seconds",
    )
    page_timeout: int = Field(
        default=30,
        ge=5,
        le=120,
        description="Playwright page navigation timeout in seconds",
    )
    crawl_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="Polite delay between page requests (seconds)",
    )

    # ------------------------------------------------------------------ #
    # Content
    # ------------------------------------------------------------------ #
    max_content_chars: int = Field(
        default=40_000,
        ge=1_000,
        le=200_000,
        description="Max characters of evidence to send to the LLM",
    )
    max_excerpt_chars: int = Field(
        default=300,
        ge=50,
        le=1_000,
        description="Max characters per source excerpt",
    )

    # ------------------------------------------------------------------ #
    # Browser
    # ------------------------------------------------------------------ #
    headless: bool = Field(
        default=True,
        description="Run Playwright Chromium in headless mode",
    )
    user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        description="Browser user-agent string",
    )

    # ------------------------------------------------------------------ #
    # Caching
    # ------------------------------------------------------------------ #
    cache_enabled: bool = Field(
        default=True,
        description="Enable local file-based cache for crawled pages",
    )
    cache_dir: Path = Field(
        default=Path("cache"),
        description="Directory for the local cache files",
    )
    cache_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Cache entry TTL in hours",
    )

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Python logging level",
    )
    log_format: Literal["text", "json"] = Field(
        default="text",
        description="Log output format: text (human-readable) or json (structured)",
    )

    # ------------------------------------------------------------------ #
    # Optional Search Provider
    # ------------------------------------------------------------------ #
    search_provider: Literal["disabled", "tavily"] = Field(
        default="disabled",
        description="Optional external search provider for supplementary data",
    )
    tavily_api_key: str | None = Field(
        default=None,
        description="Tavily API key (required only when search_provider=tavily)",
    )

    # ------------------------------------------------------------------ #
    # Output
    # ------------------------------------------------------------------ #
    default_output_path: Path = Field(
        default=Path("data/output.json"),
        description="Default path for the output file",
    )

    # ------------------------------------------------------------------ #
    # Validators
    # ------------------------------------------------------------------ #
    @field_validator("cache_dir", mode="before")
    @classmethod
    def _ensure_cache_dir(cls, v: str | Path) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p


# Singleton instance – import this everywhere in the app.
settings = Settings()  # type: ignore[call-arg]
