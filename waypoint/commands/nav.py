"""Navigation command handlers."""

from __future__ import annotations

import os
import sys

from rich.console import Console
from rich.markup import escape

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.output import err, hint, ok
from waypoint.prompts import confirm_create
from waypoint.resolver import FORCE_FLAG, NavCmd

__all__ = [
    "_nav",
    "_default_target",
    "_require_dir",
    "_offer_create",
    "_emit_target",
    "_record_origin",
    "NAV_OUT_ENV",
]

# The wrapper must run -F live so the create prompt is visible, and a live
# process cannot hand its path back over a captured stdout. It passes this env
# var and reads the resolved target from that file once the process exits.
NAV_OUT_ENV = "WP_NAV_OUT"


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
        label = alias
    else:
        target = _default_target(b, console)
        if target is None or b.default is None:
            return EXIT_ERROR
        label = b.default
    if not os.path.isdir(target):
        if not cmd.force:
            _require_dir(target, label, console)
            return EXIT_ERROR
        if not _offer_create(target, console):
            return EXIT_ERROR
    _record_origin(target)
    _emit_target(target, console)
    return EXIT_OK


def _default_target(b: store.Bookmarks, console: Console) -> str | None:
    """Resolve the default bookmark's path; print an error and return None on failure."""
    if b.default is None:
        err(console, "No default bookmark.")
        hint(console, "Set one with: [bold]wp default <alias>[/bold]")
        return None
    target = b.bookmarks.get(b.default)
    if target is None:
        err(console, f"Default bookmark {b.default!r} no longer exists.")
        return None
    return target


def _require_dir(target: str, label: str, console: Console) -> bool:
    """Report a missing target and point at the -F recovery."""
    if not os.path.isdir(target):
        err(console, f"Bookmark {label!r} points to a path that doesn't exist: {target}")
        hint(console, f"Create it with: [bold]wp {escape(label)} {FORCE_FLAG}[/bold]")
        return False
    return True


def _offer_create(target: str, console: Console) -> bool:
    """Prompt to create a missing target directory. True if it now exists."""
    if not confirm_create(target):
        return False
    try:
        os.makedirs(target, exist_ok=True)
    except OSError as e:
        err(console, f"cannot create directory {target}: {e}")
        return False
    ok(console, f"Created {target}")
    return True


def _emit_target(target: str, console: Console) -> None:
    """Hand the resolved path back to the shell.

    The wrapper runs -F live so the prompt is visible, and a live process cannot
    deliver its path over the captured stdout the cd protocol relies on. WP_NAV_OUT
    is the side channel for that case; without it -- a plain nav, or running the
    module directly -- the path goes to stdout exactly as before.
    """
    nav_out = os.environ.get(NAV_OUT_ENV)
    if nav_out:
        try:
            with open(nav_out, "w", encoding="utf-8") as fh:
                fh.write(target)
            return
        except OSError as e:
            err(console, f"cannot hand off navigation target: {e}")
            # Fall through to stdout so the wrapper still has something to read.
    sys.stdout.write(target + "\n")
