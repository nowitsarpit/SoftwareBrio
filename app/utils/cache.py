"""
Lightweight local file-based cache for crawled page content.

Avoids re-fetching the same URL during development cycles.  The cache
stores entries as JSON files keyed by URL hash, with a configurable TTL.

No external dependencies (no Redis, no SQLite) – just the filesystem.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.utils.hashing import url_hash

logger = logging.getLogger(__name__)


class PageCache:
    """
    File-based page-content cache.

    Each entry is a JSON file stored in ``cache_dir`` named ``<url_hash>.json``.
    Entries expire after ``ttl_hours`` hours.

    Parameters
    ----------
    cache_dir:
        Directory where cache files are stored.
    ttl_hours:
        How long entries remain valid.
    enabled:
        When False, all get/set calls are no-ops (cache is disabled globally).
    """

    def __init__(
        self,
        cache_dir: Path,
        ttl_hours: int = 24,
        enabled: bool = True,
    ) -> None:
        self._dir = cache_dir
        self._ttl_seconds = ttl_hours * 3600
        self._enabled = enabled
        if enabled:
            self._dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, url: str) -> dict[str, Any] | None:
        """
        Retrieve a cached entry for *url*.

        Returns
        -------
        dict | None
            The cached payload dict, or None if not found / expired.
        """
        if not self._enabled:
            return None

        cache_path = self._path_for(url)
        if not cache_path.exists():
            return None

        try:
            raw = cache_path.read_text(encoding="utf-8")
            entry: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Cache read error for %s: %s", url, exc)
            return None

        stored_at: float = entry.get("stored_at", 0.0)
        if time.time() - stored_at > self._ttl_seconds:
            logger.debug("Cache expired for %s", url)
            cache_path.unlink(missing_ok=True)
            return None

        logger.debug("Cache hit for %s", url)
        return entry.get("payload")

    def set(self, url: str, payload: dict[str, Any]) -> None:
        """
        Store *payload* for *url* in the cache.

        Parameters
        ----------
        url:
            The canonical URL being cached.
        payload:
            Arbitrary JSON-serialisable dict to store.
        """
        if not self._enabled:
            return

        cache_path = self._path_for(url)
        entry = {"url": url, "stored_at": time.time(), "payload": payload}

        try:
            cache_path.write_text(
                json.dumps(entry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug("Cached %s → %s", url, cache_path.name)
        except OSError as exc:
            logger.warning("Could not write cache for %s: %s", url, exc)

    def invalidate(self, url: str) -> None:
        """Remove a single cached entry."""
        if not self._enabled:
            return
        self._path_for(url).unlink(missing_ok=True)

    def clear(self) -> int:
        """Delete all cache files.  Returns the number deleted."""
        if not self._enabled:
            return 0
        count = 0
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)
            count += 1
        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _path_for(self, url: str) -> Path:
        return self._dir / f"{url_hash(url)}.json"
