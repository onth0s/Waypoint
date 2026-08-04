"""Shared constants for the Waypoint CLI."""

from __future__ import annotations

__all__ = [
    "TEMP_SLOT",
    "EXIT_OK",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "UNDO_STACK",
    "HISTORY_PREVIEW",
]

# Bookmark names
TEMP_SLOT: str = "temp"

# Exit codes
EXIT_OK: int = 0
EXIT_ERROR: int = 1
EXIT_USAGE: int = 2

# History depth: how many navigation origins `wp undo` can walk back through
UNDO_STACK: int = 50

# How many entries `wp history` shows by default (wp history --all shows all)
HISTORY_PREVIEW: int = 5
