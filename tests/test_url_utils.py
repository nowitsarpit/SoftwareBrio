"""
Tests for URL normalisation and domain utilities.
"""

from __future__ import annotations

import pytest

from app.crawler.url_utils import (
    deduplicate_urls,
    extract_domain,
    is_crawlable,
    is_same_domain,
    normalize_domain,
    normalize_url,
)


class TestNormalizeDomain:
    def test_bare_domain(self) -> None:
        assert normalize_domain("postman.com") == "postman.com"

    def test_https_www(self) -> None:
        assert normalize_domain("https://www.postman.com/") == "postman.com"

    def test_http_scheme(self) -> None:
        assert normalize_domain("http://postman.com") == "postman.com"

    def test_trailing_slash(self) -> None:
        assert normalize_domain("https://postman.com/") == "postman.com"

    def test_www_prefix_only(self) -> None:
        assert normalize_domain("www.postman.com") == "postman.com"

    def test_uppercase(self) -> None:
        assert normalize_domain("HTTPS://WWW.POSTMAN.COM/") == "postman.com"

    def test_with_path(self) -> None:
        assert normalize_domain("https://www.postman.com/about") == "postman.com"

    def test_supabase(self) -> None:
        assert normalize_domain("supabase.com") == "supabase.com"

    def test_vapi(self) -> None:
        assert normalize_domain("https://vapi.ai/") == "vapi.ai"

    def test_port_stripping(self) -> None:
        assert normalize_domain("http://example.com:8080/") == "example.com"


class TestNormalizeUrl:
    _BASE = "https://postman.com"

    def test_relative_url(self) -> None:
        result = normalize_url("/about", self._BASE)
        assert result == "https://postman.com/about"

    def test_absolute_url(self) -> None:
        result = normalize_url("https://postman.com/pricing", self._BASE)
        assert result == "https://postman.com/pricing"

    def test_strips_fragment(self) -> None:
        result = normalize_url("/about#team", self._BASE)
        assert result == "https://postman.com/about"

    def test_strips_query(self) -> None:
        result = normalize_url("/pricing?plan=free", self._BASE)
        assert result == "https://postman.com/pricing"

    def test_rejects_javascript(self) -> None:
        assert normalize_url("javascript:void(0)", self._BASE) is None

    def test_rejects_mailto(self) -> None:
        assert normalize_url("mailto:test@example.com", self._BASE) is None

    def test_rejects_empty(self) -> None:
        assert normalize_url("", self._BASE) is None

    def test_rejects_hash_only(self) -> None:
        assert normalize_url("#section", self._BASE) is None


class TestIsSameDomain:
    def test_exact_match(self) -> None:
        assert is_same_domain("https://postman.com/about", "postman.com")

    def test_subdomain_allowed(self) -> None:
        assert is_same_domain("https://blog.postman.com/article", "postman.com")

    def test_different_domain_rejected(self) -> None:
        assert not is_same_domain("https://example.com/about", "postman.com")

    def test_similar_domain_rejected(self) -> None:
        assert not is_same_domain("https://notpostman.com/", "postman.com")


class TestIsCrawlable:
    def test_pdf_blocked(self) -> None:
        assert not is_crawlable("https://postman.com/report.pdf", "postman.com")

    def test_image_blocked(self) -> None:
        assert not is_crawlable("https://postman.com/logo.png", "postman.com")

    def test_external_blocked(self) -> None:
        assert not is_crawlable("https://google.com/", "postman.com")

    def test_valid_page_allowed(self) -> None:
        assert is_crawlable("https://postman.com/about", "postman.com")

    def test_pricing_allowed(self) -> None:
        assert is_crawlable("https://postman.com/pricing", "postman.com")

    def test_cdn_blocked(self) -> None:
        assert not is_crawlable("https://postman.com/cdn-cgi/trace", "postman.com")


class TestDeduplicateUrls:
    def test_removes_duplicates(self) -> None:
        urls = [
            "https://postman.com/about",
            "https://postman.com/pricing",
            "https://postman.com/about",
        ]
        assert deduplicate_urls(urls) == [
            "https://postman.com/about",
            "https://postman.com/pricing",
        ]

    def test_preserves_order(self) -> None:
        urls = ["https://a.com", "https://b.com", "https://c.com"]
        assert deduplicate_urls(urls) == urls

    def test_empty(self) -> None:
        assert deduplicate_urls([]) == []
