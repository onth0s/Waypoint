"""Shared constants for the Waypoint CLI."""

from __future__ import annotations

__all__ = [
    "TEMP_SLOT",
    "EXIT_OK",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "UNDO_STACK",
    "HISTORY_PREVIEW",
    "WaypointError",
]

# Exit codes
EXIT_OK: int = 0
EXIT_ERROR: int = 1
EXIT_USAGE: int = 2

# Bookmark names
TEMP_SLOT: str = "temp"

# Base exception for all Waypoint-specific errors
class WaypointError(Exception):
    """Base class for all Waypoint exceptions."""
    exit_code: int = EXIT_ERROR

# History depth: how many navigation origins `wp undo` can walk back through
UNDO_STACK: int = 50

# How many entries `wp history` shows by default (wp history --all shows all)
HISTORY_PREVIEW: int = 5
