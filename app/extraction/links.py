"""
Link extraction from rendered HTML/DOM.

Extracts (href, anchor_text) pairs from a BeautifulSoup tree or from
a Playwright page's inner HTML string.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def extract_links_from_html(html: str, base_url: str = "") -> list[tuple[str, str]]:
    """
    Parse all anchor tags from *html* and return (href, anchor_text) pairs.

    Parameters
    ----------
    html:
        Raw or rendered HTML string.
    base_url:
        Unused here – callers should use :func:`app.crawler.url_utils.normalize_url`
        to resolve relative hrefs after this call.

    Returns
    -------
    list[tuple[str, str]]
        Each tuple contains (href, visible_anchor_text).
    """
    soup = BeautifulSoup(html, "lxml")
    links: list[tuple[str, str]] = []

    for tag in soup.find_all("a", href=True):
        if not isinstance(tag, Tag):
            continue
        href: str = str(tag["href"]).strip()
        anchor: str = tag.get_text(separator=" ", strip=True)[:200]
        if href:
            links.append((href, anchor))

    return links
