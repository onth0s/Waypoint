"""Shared constants for the Waypoint CLI."""

from __future__ import annotations

__all__ = ["TEMP_SLOT", "EXIT_OK", "EXIT_ERROR", "EXIT_USAGE"]

# Bookmark names
TEMP_SLOT: str = "temp"

# Exit codes
EXIT_OK: int = 0
EXIT_ERROR: int = 1
EXIT_USAGE: int = 2
