"""
Tests for deterministic email and contact extraction.
"""

from __future__ import annotations

import pytest

from app.extraction.contacts import extract_emails_from_html, merge_emails


class TestExtractEmailsFromHtml:
    def test_mailto_link(self) -> None:
        html = '<a href="mailto:hello@acme.io">Contact</a>'
        emails = extract_emails_from_html(html)
        assert "hello@acme.io" in emails

    def test_plain_text_email(self) -> None:
        html = "<p>Reach us at support@company.io for help.</p>"
        emails = extract_emails_from_html(html)
        assert "support@company.io" in emails

    def test_multiple_emails(self) -> None:
        html = """
        <a href="mailto:sales@acme.com">Sales</a>
        <a href="mailto:info@acme.com">Info</a>
        """
        emails = extract_emails_from_html(html)
        assert "sales@acme.com" in emails
        assert "info@acme.com" in emails

    def test_deduplication(self) -> None:
        html = """
        <a href="mailto:contact@co.com">Link 1</a>
        <a href="mailto:contact@co.com">Link 2</a>
        <p>Also: contact@co.com</p>
        """
        emails = extract_emails_from_html(html)
        assert emails.count("contact@co.com") == 1

    def test_normalisation_to_lowercase(self) -> None:
        html = '<a href="mailto:Hello@Acme.IO">Contact</a>'
        emails = extract_emails_from_html(html)
        assert "hello@acme.io" in emails

    def test_rejects_example_domain(self) -> None:
        html = '<a href="mailto:user@example.com">Contact</a>'
        emails = extract_emails_from_html(html)
        assert "user@example.com" not in emails

    def test_empty_html(self) -> None:
        assert extract_emails_from_html("") == []

    def test_no_emails(self) -> None:
        html = "<p>We have no contact information here.</p>"
        assert extract_emails_from_html(html) == []

    def test_mailto_with_query_params(self) -> None:
        html = '<a href="mailto:press@co.com?subject=Hello">Press</a>'
        emails = extract_emails_from_html(html)
        assert "press@co.com" in emails

    def test_rejects_sentry_domain(self) -> None:
        html = "<script>Sentry.init({dsn: 'noreply@sentry.io'})</script>"
        emails = extract_emails_from_html(html)
        assert "noreply@sentry.io" not in emails

    def test_strips_unicode_escape_artifacts(self) -> None:
        html = r'var json = "{\"email\": \"\u003einfo@postman.com\"}";'
        emails = extract_emails_from_html(html)
        assert "info@postman.com" in emails
        assert "u003einfo@postman.com" not in emails

    def test_escaped_html_entities(self) -> None:
        html = '<p>&gt;support@company.org&lt;</p>'
        emails = extract_emails_from_html(html)
        assert "support@company.org" in emails

    def test_rejects_js_asset_bundle_filenames(self) -> None:
        html = '<script src="vue@3.4.15.min.3a7e0323bd7d.js"></script><p>Contact vue-shadow-dom@4.2.0.c6ed52f5c4de.mjs</p>'
        emails = extract_emails_from_html(html)
        assert emails == []


class TestMergeEmails:
    def test_merges_multiple_lists(self) -> None:
        lists = [["a@b.com", "c@d.com"], ["c@d.com", "e@f.com"]]
        merged = merge_emails(lists)
        assert set(merged) == {"a@b.com", "c@d.com", "e@f.com"}

    def test_empty_lists(self) -> None:
        assert merge_emails([[], []]) == []

    def test_single_list(self) -> None:
        assert merge_emails([["a@b.com"]]) == ["a@b.com"]

    def test_normalises_case(self) -> None:
        result = merge_emails([["A@B.COM"]])
        assert "a@b.com" in result
