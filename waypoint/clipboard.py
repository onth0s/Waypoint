"""Clipboard utilities for Waypoint CLI."""

from __future__ import annotations

import os

import pyperclip


def clipboard_path() -> str | None:
    """Clipboard text if it is an existing path (paste from Explorer), else None."""
    try:
        raw = pyperclip.paste()
    except (OSError, RuntimeError):
        return None
    if not raw:
        return None
    text: str = raw.strip().strip('"')
    if os.path.isdir(text):
        return text
    if os.path.isfile(text):
        return os.path.dirname(text)
    return None
