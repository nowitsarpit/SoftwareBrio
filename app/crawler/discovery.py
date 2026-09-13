"""
Page discovery and relevance scoring.

Given a list of discovered links (URL + anchor text), this module assigns
a relevance score to each candidate and returns a prioritised list for
crawling.  The logic is deterministic and testable without a network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.crawler.url_utils import is_crawlable, normalize_url


# ---------------------------------------------------------------------------
# Scoring tables
# ---------------------------------------------------------------------------

# (pattern, score) – patterns are matched against the lowercase URL path.
# Scores accumulate; the first matching group dominates.
_PATH_SCORES: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"/(about|about-us|our-story|who-we-are)(/|$)"), 85),
    (re.compile(r"/(team|leadership|founders|executives|management|people)(/|$)"), 95),
    (re.compile(r"/(company|about-company)(/|$)"), 80),
    (re.compile(r"/(contact|contact-us|get-in-touch|reach-us)(/|$)"), 75),
    (re.compile(r"/(sales|talk-to-sales|book-demo|demo|get-demo)(/|$)"), 70),
    (re.compile(r"/(pricing|plans|plan)(/|$)"), 70),
    (re.compile(r"/(customers|case-studies|success-stories|testimonials)(/|$)"), 65),
    (re.compile(r"/(solutions|use-cases|industries)(/|$)"), 60),
    (re.compile(r"/(product|platform|features|overview)(/|$)"), 55),
    (re.compile(r"/(enterprise|for-enterprise|business)(/|$)"), 55),
    (re.compile(r"/(partners|partnerships)(/|$)"), 45),
    (re.compile(r"/(careers|jobs|open-positions)(/|$)"), 35),
    (re.compile(r"/(press|media|news-room|newsroom)(/|$)"), 30),
    (re.compile(r"/(blog|articles|resources|insights)(/|$)"), 20),
    (re.compile(r"/(docs|documentation|developer|api)(/|$)"), 15),
    (re.compile(r"/(privacy|privacy-policy|cookie|terms|legal|tos|gdpr)(/|$)"), -50),
    (re.compile(r"/(sitemap|robots|404|error)(/|$)"), -100),
]

# Anchor-text score bonuses.
_ANCHOR_KEYWORDS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\b(leadership|team|founders?|executives?)\b", re.I), 20),
    (re.compile(r"\b(about|company|who we are|our story)\b", re.I), 15),
    (re.compile(r"\b(contact|get in touch|talk to us)\b", re.I), 12),
    (re.compile(r"\b(pricing|plans?)\b", re.I), 12),
    (re.compile(r"\b(customers?|case studi)\b", re.I), 10),
    (re.compile(r"\b(solutions?|use cases?)\b", re.I), 8),
    (re.compile(r"\b(platform|product|features?)\b", re.I), 6),
    (re.compile(r"\b(blog|article|news)\b", re.I), -5),
    (re.compile(r"\b(privacy|terms|legal|cookie)\b", re.I), -30),
]

# Minimum score for a page to be included in the crawl queue.
_MIN_SCORE: int = 0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ScoredLink:
    """A candidate URL with its relevance score and metadata."""

    score: int
    url: str
    anchor_text: str = ""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def score_url(url: str, anchor_text: str = "") -> int:
    """
    Calculate an integer relevance score for a candidate URL.

    Parameters
    ----------
    url:
        The normalised absolute URL.
    anchor_text:
        The visible anchor text for the link (optional).

    Returns
    -------
    int
        Relevance score.  Higher is more relevant.
    """
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    score = 0

    for pattern, points in _PATH_SCORES:
        if pattern.search(path):
            score += points

    anchor_lower = anchor_text.strip().lower()
    for pattern, points in _ANCHOR_KEYWORDS:
        if pattern.search(anchor_lower):
            score += points

    # Root / homepage gets a neutral score – always crawled separately.
    if path in ("", "/"):
        score = 100

    return score


def prioritize_links(
    raw_links: list[tuple[str, str]],
    base_url: str,
    target_domain: str,
    max_pages: int,
) -> list[ScoredLink]:
    """
    Filter, score, and rank a list of (url, anchor_text) pairs.

    Parameters
    ----------
    raw_links:
        List of (href, anchor_text) tuples as found on the page.
    base_url:
        The absolute base URL used to resolve relative hrefs.
    target_domain:
        The apex domain being crawled (used for same-domain filtering).
    max_pages:
        Maximum number of pages to return.

    Returns
    -------
    List[ScoredLink]
        Sorted descending by score, at most *max_pages* entries.
    """
    seen_urls: set[str] = set()
    scored: list[ScoredLink] = []

    for href, anchor in raw_links:
        normalised = normalize_url(href, base_url)
        if not normalised:
            continue
        if not is_crawlable(normalised, target_domain):
            continue
        if normalised in seen_urls:
            continue
        seen_urls.add(normalised)

        s = score_url(normalised, anchor)
        if s >= _MIN_SCORE:
            scored.append(ScoredLink(score=s, url=normalised, anchor_text=anchor))

    # Sort descending by score (highest relevance first).
    scored.sort(key=lambda sl: sl.score, reverse=True)
    return scored[:max_pages]
