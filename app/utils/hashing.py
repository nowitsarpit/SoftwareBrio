"""
Content hashing utilities for the cache layer.

All functions are pure, deterministic, and dependency-free.
"""

from __future__ import annotations

import hashlib


def url_hash(url: str) -> str:
    """Return a short SHA-256 hex digest for a URL (used as cache key)."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def content_hash(content: str) -> str:
    """Return a short SHA-256 hex digest for arbitrary string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
