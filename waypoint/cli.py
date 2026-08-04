"""Waypoint CLI: dispatch and entry point.

Stdout protocol (load-bearing, consumed by the `wp` PowerShell wrapper in
install.ps1): a navigation invocation prints ONLY the resolved absolute path
to stdout and exits 0 — the wrapper cds when stdout is exactly one line that
is an existing path. Everything else is human output rendered via rich on
stdout (never stderr, since PowerShell shows native stderr as red error
records). The bare nav path is the single sanctioned exception to AGENTS.md's
"use rich for all output" rule: it is machine protocol, not text for a human.
"""

from __future__ import annotations

import os
import sys

from rich.console import Console

from waypoint import store
from waypoint.commands import (
    _add,
    _config,
    _default,
    _help,
    _history,
    _ls,
    _nav,
    _open,
    _rm,
    _set,
    _store,
    _undo,
)
from waypoint.constants import EXIT_ERROR, EXIT_USAGE
from waypoint.output import err, hint
from waypoint.prompts import _Cancelled
from waypoint.resolver import Command, UsageError, parse_args


def main(argv: list[str] | None = None) -> int:
    # The `wp` wrapper captures stdout (pipe), which would make rich drop color;
    # it signals an interactive session via WP_FORCE_COLOR so end users still
    # get colored output (AGENTS.md). Constructed per call so pytest's capsys
    # captures it.
    force = os.environ.get("WP_FORCE_COLOR") == "1"
    console = Console(
        force_terminal=force,
        color_system="standard" if force else None,
        no_color=False if force else None,  # override ambient NO_COLOR when forced
        # legacy_windows routes through win32 console API calls that silently
        # no-op on pipes (the wrapper captures stdout) — force ANSI writes.
        legacy_windows=False if force else None,
        # Default highlight bolds every balanced "(...)" via ReprHighlighter,
        # injecting escape codes mid-text — noise for end users and it can make
        # a single rich line trip the wrapper's Test-Path. Off.
        highlight=False,
    )
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        cmd = parse_args(args)
        return dispatch(cmd, console)
    except _Cancelled:
        console.print("Cancelled.")
        return EXIT_ERROR
    except UsageError as e:
        err(console, e)
        hint(console, "Run [bold]wp help[/bold] for usage.")
        return EXIT_USAGE
    except store.StoreError as e:
        err(console, e)
        return EXIT_ERROR
    except store.BookmarkNotFoundError as e:
        err(console, e)
        return EXIT_ERROR


def dispatch(cmd: Command, console: Console) -> int:
    """Route a parsed command to its handler."""
    if cmd.kind == "nav":
        return _nav(cmd, console)
    if cmd.kind == "undo":
        return _undo(cmd, console)
    if cmd.kind == "history":
        return _history(cmd, console)
    if cmd.kind == "add":
        return _add(cmd, console)
    if cmd.kind == "rm":
        return _rm(cmd, console)
    if cmd.kind == "ls":
        return _ls(console)
    if cmd.kind == "default":
        return _default(cmd, console)
    if cmd.kind == "set":
        return _set(cmd, console)
    if cmd.kind == "config":
        return _config(cmd, console)
    if cmd.kind == "store":
        return _store(cmd, console)
    if cmd.kind == "help":
        return _help(console)
    if cmd.kind in ("explorer", "code"):
        return _open(cmd.kind, console)
    raise UsageError(f"unknown command: {cmd.kind}")  # safety net for future command kinds
