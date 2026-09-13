"""
URL normalisation, domain filtering, and related helpers.

All functions are pure (no side effects) and fully typed so they can be
tested in isolation without a browser or network.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# URL schemes we are willing to follow.
_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Paths that should never be crawled.
_SKIP_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".pdf", ".docx", ".xlsx", ".pptx", ".zip", ".tar", ".gz",
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
        ".mp4", ".webm", ".mp3", ".ogg", ".woff", ".woff2", ".ttf",
        ".eot", ".css", ".js", ".json", ".xml", ".rss", ".atom",
    }
)

_SKIP_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"/cdn-cgi/",
        r"/wp-content/",
        r"/wp-includes/",
        r"/__next/",
        r"/_next/",
        r"/static/",
        r"/assets/",
        r"/images/",
        r"/fonts/",
        r"/favicon",
        r"\?.*utm_",  # UTM-tracked links – usually same content
    ]
]


# ---------------------------------------------------------------------------
# Core normalisation
# ---------------------------------------------------------------------------


def normalize_domain(raw: str) -> str:
    """
    Normalise an arbitrary domain/URL input to a bare hostname (no scheme,
    no path, no www prefix).

    Examples
    --------
    >>> normalize_domain("https://www.postman.com/")
    'postman.com'
    >>> normalize_domain("www.postman.com")
    'postman.com'
    >>> normalize_domain("postman.com")
    'postman.com'
    """
    raw = raw.strip().lower()  # Lowercase first so urlparse sees a valid scheme.
    # Ensure we have a scheme so urlparse works correctly.
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path
    # Strip port if present.
    host = host.split(":")[0]
    # Remove www. prefix – we'll normalise to the apex domain.
    if host.startswith("www."):
        host = host[4:]
    return host.lower().rstrip(".")


def build_base_url(domain: str) -> str:
    """Return the HTTPS homepage URL for a normalised domain."""
    return f"https://{domain}"


def normalize_url(url: str, base_url: str) -> str | None:
    """
    Normalise a potentially relative URL against *base_url*.

    Returns ``None`` if the URL should be rejected (wrong scheme, external
    domain, file extension, etc.).
    """
    if not url:
        return None
    url = url.strip()

    # Strip fragments.
    url = url.split("#")[0]

    if not url:
        return None

    # Skip non-navigatable targets.
    if url.startswith(("javascript:", "mailto:", "tel:", "data:", "blob:")):
        return None

    # Resolve relative URLs.
    full_url = urljoin(base_url, url)

    parsed = urlparse(full_url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return None

    # Drop query string – keeps dedup cleaner; most company pages don't need QS.
    normalised = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", "", "")
    )

    return normalised


def extract_domain(url: str) -> str:
    """Return the bare hostname from a full URL."""
    parsed = urlparse(url)
    host = parsed.netloc.split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def is_same_domain(url: str, target_domain: str) -> bool:
    """
    Return True if *url* belongs to *target_domain* or one of its subdomains.

    We allow crawling e.g. ``careers.postman.com`` which could reveal team info,
    but we stop at completely different apex domains.
    """
    url_domain = extract_domain(url)
    # Exact match or subdomain match.
    return url_domain == target_domain or url_domain.endswith(f".{target_domain}")


def is_crawlable(url: str, target_domain: str) -> bool:
    """
    Return True only if the URL is safe to crawl (same domain, allowed scheme,
    no blocked extension/path).
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    if not is_same_domain(url, target_domain):
        return False

    path_lower = parsed.path.lower()

    # Block known binary/asset extensions.
    for ext in _SKIP_EXTENSIONS:
        if path_lower.endswith(ext):
            return False

    # Block CDN/asset paths.
    for pattern in _SKIP_PATH_PATTERNS:
        if pattern.search(url):
            return False

    return True


def deduplicate_urls(urls: list[str]) -> list[str]:
    """Return *urls* with duplicates removed, preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result
