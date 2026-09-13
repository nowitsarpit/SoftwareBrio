"""
HTML content extraction and cleaning.

Converts a rendered HTML page into compact, LLM-friendly plain text by:
  - Removing scripts, styles, SVGs, iframes, and other non-content elements.
  - Stripping hidden elements where detectable.
  - Preserving semantic structure (headings, paragraphs, lists).
  - Normalising whitespace.
  - Truncating to a configured maximum length.

The goal is high information density at minimal token cost.
"""

from __future__ import annotations

import re
import unicodedata

from bs4 import BeautifulSoup, Comment, NavigableString, Tag


# ---------------------------------------------------------------------------
# Elements to remove unconditionally
# ---------------------------------------------------------------------------

_REMOVE_TAGS: frozenset[str] = frozenset(
    {
        "script", "style", "svg", "iframe", "noscript", "canvas",
        "video", "audio", "object", "embed", "applet", "map",
        "head",  # <head> contains no visible content
        "meta", "link", "base",
    }
)

# Role / class patterns that indicate navigation / footer / cookie boilerplate.
_SKIP_ROLES: frozenset[str] = frozenset({"navigation", "menubar", "banner", "complementary"})

_SKIP_CLASS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bnav(bar|igation)?\b",
        r"\bheader\b",
        r"\bfooter\b",
        r"\bcookie(-banner|-consent|s)?\b",
        r"\bpopup\b",
        r"\bmodal\b",
        r"\boverlay\b",
        r"\bads?\b",
        r"\badvert(isement)?\b",
        r"\btoast\b",
        r"\bannounc(e|ement)\b",
        r"\bsidebar\b",
        r"\bbreadcrumb\b",
        r"\bpagination\b",
    ]
]

_SKIP_ID_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bnav\b",
        r"\bheader\b",
        r"\bfooter\b",
        r"\bcookie\b",
        r"\bsidebar\b",
    ]
]


def _should_skip_element(tag: Tag) -> bool:
    """Return True if *tag* looks like boilerplate that should be removed."""
    # ARIA role check.
    role = tag.get("role", "")
    if isinstance(role, list):
        role = " ".join(role)
    if role in _SKIP_ROLES:
        return True

    # Hidden via style or hidden attribute.
    style = tag.get("style", "")
    if isinstance(style, list):
        style = " ".join(style)
    if "display:none" in style.replace(" ", "").lower():
        return True
    if "visibility:hidden" in style.replace(" ", "").lower():
        return True
    if tag.get("hidden"):
        return True
    if tag.get("aria-hidden") == "true":
        return True

    # Class-based heuristics.
    classes = tag.get("class", [])
    if isinstance(classes, str):
        classes = classes.split()
    class_str = " ".join(classes)
    for pattern in _SKIP_CLASS_PATTERNS:
        if pattern.search(class_str):
            return True

    # ID-based heuristics.
    elem_id = tag.get("id", "")
    if isinstance(elem_id, list):
        elem_id = " ".join(elem_id)
    for pattern in _SKIP_ID_PATTERNS:
        if pattern.search(str(elem_id)):
            return True

    return False


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _tag_to_text(tag: Tag, depth: int = 0) -> str:
    """
    Recursively extract text from *tag* with minimal markdown-like formatting.
    """
    name = tag.name or ""

    if name in _REMOVE_TAGS:
        return ""

    if _should_skip_element(tag) and depth > 0:
        return ""

    parts: list[str] = []

    for child in tag.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            text = child.strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag):
            child_text = _tag_to_text(child, depth + 1)
            if child_text:
                if child.name in ("h1", "h2"):
                    parts.append(f"\n## {child_text.strip()}\n")
                elif child.name in ("h3", "h4", "h5", "h6"):
                    parts.append(f"\n### {child_text.strip()}\n")
                elif child.name in ("p", "div", "section", "article"):
                    parts.append(f"\n{child_text.strip()}\n")
                elif child.name in ("li",):
                    parts.append(f"\n- {child_text.strip()}")
                elif child.name in ("br",):
                    parts.append("\n")
                else:
                    parts.append(child_text)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_clean_text(html: str, max_chars: int | None = None) -> str:
    """
    Convert raw or rendered HTML into clean, compact plain text.

    Parameters
    ----------
    html:
        Full HTML string (from Playwright or requests).
    max_chars:
        If provided, truncate the result to this many characters.

    Returns
    -------
    str
        Clean text suitable for LLM consumption.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove outright noise tags.
    for tag in soup.find_all(_REMOVE_TAGS):
        tag.decompose()

    # Remove HTML comments.
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Extract from <main> or <body>, whichever is more specific.
    root: Tag | None = soup.find("main") or soup.find("article") or soup.find("body")  # type: ignore[assignment]
    if root is None:
        root = soup  # type: ignore[assignment]

    raw_text = _tag_to_text(root)

    # Normalise unicode.
    raw_text = unicodedata.normalize("NFKC", raw_text)

    # Collapse excessive whitespace / blank lines.
    raw_text = re.sub(r"[ \t]+", " ", raw_text)
    raw_text = re.sub(r"\n{3,}", "\n\n", raw_text)
    raw_text = raw_text.strip()

    if max_chars and len(raw_text) > max_chars:
        raw_text = raw_text[:max_chars] + "\n\n[content truncated]"

    return raw_text


def get_page_title(html: str) -> str:
    """Extract the <title> text from an HTML string."""
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True)
    # Fallback: first <h1>.
    h1 = soup.find("h1")
    if h1 and isinstance(h1, Tag):
        return h1.get_text(strip=True)[:120]
    return ""


def deduplicate_content(pages: list[str]) -> str:
    """
    Merge content from multiple pages, removing near-duplicate paragraphs.

    This prevents the LLM from seeing the same navigation text repeated
    across every page.
    """
    seen_hashes: set[int] = set()
    unique_parts: list[str] = []

    for page_text in pages:
        for paragraph in page_text.split("\n\n"):
            normalized = re.sub(r"\s+", " ", paragraph.strip().lower())
            if len(normalized) < 30:
                # Skip very short / likely boilerplate lines.
                continue
            h = hash(normalized)
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_parts.append(paragraph.strip())

    return "\n\n".join(unique_parts)
