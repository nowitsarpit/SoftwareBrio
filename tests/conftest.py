"""
pytest configuration and shared fixtures.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require a real network connection "
        "(deselect with -m 'not integration')",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests that are expected to run slowly",
    )
