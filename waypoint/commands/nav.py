"""Navigation command handlers."""

from __future__ import annotations

import os
import sys

from rich.console import Console

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.output import err, hint
from waypoint.resolver import NavCmd

__all__ = ["_nav", "_default_target", "_require_dir", "_record_origin"]


def _record_origin(target: str) -> None:
    """Push the pre-jump cwd onto the undo stack (skip no-move / duplicates)."""
    origin = os.getcwd()
    if os.path.normcase(origin) == os.path.normcase(target):
        return
    entries = store.load_history()
    if entries and os.path.normcase(entries[-1]) == os.path.normcase(origin):
        return
    store.save_history(entries + [origin])


def _nav(cmd: NavCmd, console: Console) -> int:
    b = store.load_bookmarks()
    if cmd.alias is not None:
        alias = cmd.alias
        target = b.bookmarks.get(alias)
        if target is None:
            err(console, f"No bookmark {alias!r}.")
            hint(console, "Run [bold]wp ls[/bold] to see bookmarks.")
            return EXIT_ERROR
        if not _require_dir(target, alias, console):
            return EXIT_ERROR
    else:
        target = _default_target(b, console)
        if target is None or b.default is None:
            return EXIT_ERROR
        if not _require_dir(target, b.default, console):
            return EXIT_ERROR
    _record_origin(target)
    sys.stdout.write(target + "\n")
    return EXIT_OK


def _default_target(b: store.Bookmarks, console: Console) -> str | None:
    """Resolve the default bookmark's path; print an error and return None on failure."""
    if b.default is None:
        err(console, "No default bookmark. Set one with: [bold]wp default <alias>[/bold]")
        return None
    target = b.bookmarks.get(b.default)
    if target is None:
        err(console, f"Default bookmark {b.default!r} no longer exists.")
        return None
    return target


def _require_dir(target: str, label: str, console: Console) -> bool:
    if not os.path.isdir(target):
        err(console, f"Bookmark {label!r} points to a path that doesn't exist: {target}")
        return False
    return True
