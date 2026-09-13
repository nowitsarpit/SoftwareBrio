"""
Tests for HTML content extraction and cleaning.
"""

from __future__ import annotations

import pytest

from app.extraction.content import (
    deduplicate_content,
    extract_clean_text,
    get_page_title,
)


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Acme Corp - We Build Things</title>
  <script>console.log("tracking");</script>
  <style>body { color: red; }</style>
</head>
<body>
  <nav id="nav">
    <a href="/">Home</a>
    <a href="/about">About</a>
  </nav>
  <main>
    <h1>We build the best widgets</h1>
    <p>Acme Corp is a leading provider of widget solutions for enterprise teams.</p>
    <ul>
      <li>Fast delivery</li>
      <li>24/7 support</li>
    </ul>
  </main>
  <footer>
    <p>© 2024 Acme Corp. All rights reserved.</p>
  </footer>
</body>
</html>
"""


class TestExtractCleanText:
    def test_removes_scripts(self) -> None:
        text = extract_clean_text(SAMPLE_HTML)
        assert "console.log" not in text
        assert "tracking" not in text

    def test_removes_styles(self) -> None:
        text = extract_clean_text(SAMPLE_HTML)
        assert "color: red" not in text

    def test_preserves_main_content(self) -> None:
        text = extract_clean_text(SAMPLE_HTML)
        assert "best widgets" in text
        assert "leading provider" in text

    def test_preserves_list_items(self) -> None:
        text = extract_clean_text(SAMPLE_HTML)
        assert "Fast delivery" in text
        assert "24/7 support" in text

    def test_truncation(self) -> None:
        text = extract_clean_text(SAMPLE_HTML, max_chars=50)
        assert len(text) <= 80  # slight slack for "[content truncated]" suffix
        assert "truncated" in text

    def test_no_excessive_blank_lines(self) -> None:
        text = extract_clean_text(SAMPLE_HTML)
        assert "\n\n\n" not in text

    def test_empty_html(self) -> None:
        text = extract_clean_text("")
        assert isinstance(text, str)

    def test_strips_svg(self) -> None:
        html = "<body><svg><path d='M0 0'/></svg><p>Real content</p></body>"
        text = extract_clean_text(html)
        assert "path" not in text
        assert "Real content" in text


class TestGetPageTitle:
    def test_extracts_title_tag(self) -> None:
        title = get_page_title(SAMPLE_HTML)
        assert "Acme Corp" in title

    def test_fallback_to_h1(self) -> None:
        html = "<html><body><h1>Main Heading</h1></body></html>"
        assert get_page_title(html) == "Main Heading"

    def test_empty_html(self) -> None:
        assert get_page_title("") == ""


class TestDeduplicateContent:
    def test_removes_duplicate_paragraphs(self) -> None:
        pages = [
            "Repeated navigation header text\n\nReal content about the company and its products.\n\nRepeated navigation header text",
            "Repeated navigation header text\n\nMore unique information about their pricing plans.\n\nRepeated navigation header text",
        ]
        result = deduplicate_content(pages)
        # Unique content from both pages should appear
        assert result.lower().count("real content about the company") == 1
        assert result.lower().count("more unique information about their pricing") == 1
        # Duplicate nav should appear only once
        assert result.lower().count("repeated navigation header text") == 1

    def test_empty_pages(self) -> None:
        assert deduplicate_content([]) == ""

    def test_single_page(self) -> None:
        result = deduplicate_content(["This is a meaningful paragraph with enough length."])
        assert "meaningful paragraph" in result
