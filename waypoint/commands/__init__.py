"""Command handlers for the Waypoint CLI.

Package init exposing all command handlers and clipboard utilities for test compatibility.
"""

from __future__ import annotations

import pyperclip

from waypoint import clipboard
from waypoint.commands.bookmarks import _add, _default, _ls, _rm, _set, _set_temp_slot
from waypoint.commands.config import _config, _store
from waypoint.commands.history import _history, _undo
from waypoint.commands.launcher import _help, _open
from waypoint.commands.nav import _default_target, _nav, _record_origin, _require_dir

__all__ = [
    "_add",
    "_config",
    "_default",
    "_default_target",
    "_help",
    "_history",
    "_ls",
    "_nav",
    "_open",
    "_record_origin",
    "_require_dir",
    "_rm",
    "_set",
    "_set_temp_slot",
    "_store",
    "_undo",
    "clipboard_path",
    "pyperclip",
]


def clipboard_path() -> str | None:
    """Clipboard text if it is an existing path (paste from Explorer), else None."""
    return clipboard.clipboard_path()
