"""
Top-level runner script for the Lead Enrichment Pipeline.

Usage:
  python run.py --input data/input.json --dry-run
  python run.py --domains postman.com supabase.com vapi.ai
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure workspace root is in sys.path
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.main import main

if __name__ == "__main__":
    main()
