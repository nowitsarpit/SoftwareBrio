"""
Tests for page discovery scoring and link prioritisation.
"""

from __future__ import annotations

import pytest

from app.crawler.discovery import ScoredLink, prioritize_links, score_url


class TestScoreUrl:
    def test_homepage_scores_high(self) -> None:
        assert score_url("https://postman.com/") == 100
        assert score_url("https://postman.com") == 100

    def test_team_scores_highest(self) -> None:
        about = score_url("https://postman.com/about")
        team = score_url("https://postman.com/team")
        assert team > about

    def test_about_scores_high(self) -> None:
        assert score_url("https://postman.com/about") >= 70

    def test_privacy_scores_negative(self) -> None:
        assert score_url("https://postman.com/privacy-policy") < 0

    def test_blog_scores_lower_than_about(self) -> None:
        blog = score_url("https://postman.com/blog/post-1")
        about = score_url("https://postman.com/about")
        assert about > blog

    def test_anchor_text_bonus(self) -> None:
        base = score_url("https://postman.com/random")
        with_anchor = score_url("https://postman.com/random", "About Us")
        assert with_anchor > base

    def test_leadership_anchor_bonus(self) -> None:
        score = score_url("https://postman.com/people", "Leadership Team")
        assert score > 80


class TestPrioritizeLinks:
    _BASE = "https://postman.com"
    _DOMAIN = "postman.com"

    def test_filters_external_links(self) -> None:
        links = [
            ("https://google.com/", "Google"),
            ("/about", "About"),
        ]
        result = prioritize_links(links, self._BASE, self._DOMAIN, max_pages=10)
        urls = [sl.url for sl in result]
        assert not any("google.com" in u for u in urls)
        assert any("/about" in u for u in urls)

    def test_filters_pdf_links(self) -> None:
        links = [("/report.pdf", "Download"), ("/about", "About")]
        result = prioritize_links(links, self._BASE, self._DOMAIN, max_pages=10)
        urls = [sl.url for sl in result]
        assert not any(".pdf" in u for u in urls)

    def test_respects_max_pages(self) -> None:
        links = [(f"/page-{i}", f"Page {i}") for i in range(20)]
        result = prioritize_links(links, self._BASE, self._DOMAIN, max_pages=5)
        assert len(result) <= 5

    def test_deduplicates(self) -> None:
        links = [("/about", "About"), ("/about", "About Us")]
        result = prioritize_links(links, self._BASE, self._DOMAIN, max_pages=10)
        urls = [sl.url for sl in result]
        assert len(urls) == len(set(urls))

    def test_higher_score_comes_first(self) -> None:
        links = [
            ("/blog/post", "Random Article"),
            ("/team", "Our Team"),
            ("/about", "About"),
        ]
        result = prioritize_links(links, self._BASE, self._DOMAIN, max_pages=10)
        assert len(result) >= 2
        # Team or About should rank above blog
        top_urls = [sl.url for sl in result[:2]]
        assert any("team" in u or "about" in u for u in top_urls)
