"""
Structured logging configuration for the lead-enrichment pipeline.

Sets up a human-readable (or JSON) logger that includes timestamps,
log level, and module name.  Never logs secrets or sensitive data.
"""

from __future__ import annotations

import logging
import sys
from typing import Literal


_COLOUR_CODES: dict[str, str] = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_RESET = "\033[0m"


class _ColourFormatter(logging.Formatter):
    """Add ANSI colour codes to the level name for readability in a terminal."""

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOUR_CODES.get(record.levelname, "")
        record.levelname = f"{colour}{record.levelname:<8}{_RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    fmt: Literal["text", "json"] = "text",
) -> None:
    """
    Configure the root logger for the application.

    Parameters
    ----------
    level:
        Standard Python logging level name (e.g. "INFO", "DEBUG").
    fmt:
        "text" for human-readable output; "json" for structured JSON lines
        (useful when aggregating logs with a tool like Loki or CloudWatch).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    if fmt == "json":
        try:
            import json_log_formatter  # type: ignore[import]
            formatter: logging.Formatter = json_log_formatter.JSONFormatter()
        except ImportError:
            # Fall back to text if the optional package is missing.
            formatter = _ColourFormatter(
                fmt="%(asctime)s %(levelname)s %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
    else:
        formatter = _ColourFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Quiet noisy third-party loggers.
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
