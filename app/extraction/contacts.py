"""
Deterministic contact / email extraction.

Emails are extracted by regex before the LLM is invoked.  The LLM must
NOT be responsible for discovering obvious emails that deterministic
parsing can find.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Standard email regex – RFC-5322 inspired but practical.
_EMAIL_PATTERN: re.Pattern[str] = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Patterns that indicate false positives (common in template strings).
_EMAIL_BLACKLIST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"example\.com$", re.IGNORECASE),
    re.compile(r"yourdomain\.com$", re.IGNORECASE),
    re.compile(r"domain\.com$", re.IGNORECASE),
    re.compile(r"email@email", re.IGNORECASE),
    re.compile(r"user@host", re.IGNORECASE),
    re.compile(r"\.png$", re.IGNORECASE),
    re.compile(r"\.jpg$", re.IGNORECASE),
    re.compile(r"sentry\.io$", re.IGNORECASE),
    re.compile(r"w3\.org$", re.IGNORECASE),
    re.compile(r"schema\.org$", re.IGNORECASE),
]

# Maximum length for a valid email address.
_MAX_EMAIL_LENGTH: int = 254


def _is_valid_email(email: str) -> bool:
    """Basic sanity checks for an extracted email address."""
    if len(email) > _MAX_EMAIL_LENGTH:
        return False
    if "@" not in email:
        return False
    local, _, domain = email.rpartition("@")
    if not local or not domain:
        return False
    if "." not in domain:
        return False
    for pattern in _EMAIL_BLACKLIST_PATTERNS:
        if pattern.search(email):
            return False
    return True


def _normalize_email(email: str) -> str:
    """Lowercase and strip an email address."""
    return email.strip().lower()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_emails_from_html(html: str) -> list[str]:
    """
    Extract all public email addresses from a rendered HTML page.

    Combines two strategies:
    1. ``mailto:`` links – highest confidence.
    2. Regex scan of visible text – catches emails written as plain text.

    Parameters
    ----------
    html:
        Rendered HTML string.

    Returns
    -------
    list[str]
        Deduplicated, lowercased email addresses found on the page.
    """
    soup = BeautifulSoup(html, "lxml")
    collected: set[str] = set()

    # Strategy 1: mailto: links.
    for tag in soup.find_all("a", href=True):
        href: str = str(tag.get("href", "")).strip()
        if href.lower().startswith("mailto:"):
            raw = href[7:].split("?")[0]  # strip query params
            raw = unquote(raw).strip()
            emails = _EMAIL_PATTERN.findall(raw)
            for email in emails:
                if _is_valid_email(email):
                    collected.add(_normalize_email(email))

    # Strategy 2: regex scan of all text nodes.
    # We use the raw HTML rather than parsed text to catch obfuscated patterns.
    text_content = soup.get_text(" ")
    for email in _EMAIL_PATTERN.findall(text_content):
        if _is_valid_email(email):
            collected.add(_normalize_email(email))

    # Also scan raw HTML for mailto: occurrences that BeautifulSoup might miss.
    for email in _EMAIL_PATTERN.findall(html):
        if _is_valid_email(email):
            collected.add(_normalize_email(email))

    return sorted(collected)


def merge_emails(email_lists: list[list[str]]) -> list[str]:
    """
    Merge and deduplicate email lists from multiple pages.

    Parameters
    ----------
    email_lists:
        One list per crawled page.

    Returns
    -------
    list[str]
        Sorted, deduplicated email addresses.
    """
    merged: set[str] = set()
    for emails in email_lists:
        for email in emails:
            normalised = _normalize_email(email)
            if _is_valid_email(normalised):
                merged.add(normalised)
    return sorted(merged)
