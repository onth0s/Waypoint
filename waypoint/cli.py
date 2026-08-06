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
from waypoint.commands.bookmarks import _add, _default, _get, _ls, _rm, _set
from waypoint.commands.config import _config, _store
from waypoint.commands.history import _history, _record_history_entry, _undo
from waypoint.commands.launcher import _help, _open
from waypoint.commands.nav import _nav
from waypoint.constants import EXIT_ERROR, EXIT_USAGE
from waypoint.output import err, hint
from waypoint.prompts import _Cancelled
from waypoint.resolver import (
    AddCmd,
    Command,
    ConfigCmd,
    DefaultCmd,
    GetCmd,
    HelpCmd,
    HistoryCmd,
    LsCmd,
    NavCmd,
    OpenCmd,
    RecordHistoryCmd,
    RmCmd,
    SetCmd,
    StoreCmd,
    UndoCmd,
    UsageError,
    parse_args,
)


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
    if isinstance(cmd, RecordHistoryCmd):
        return _record_history_entry(cmd)
    if isinstance(cmd, NavCmd):
        return _nav(cmd, console)
    if isinstance(cmd, UndoCmd):
        return _undo(cmd, console)
    if isinstance(cmd, HistoryCmd):
        return _history(cmd, console)
    if isinstance(cmd, AddCmd):
        return _add(cmd, console)
    if isinstance(cmd, RmCmd):
        return _rm(cmd, console)
    if isinstance(cmd, LsCmd):
        return _ls(console)
    if isinstance(cmd, DefaultCmd):
        return _default(cmd, console)
    if isinstance(cmd, SetCmd):
        return _set(cmd, console)
    if isinstance(cmd, GetCmd):
        return _get(cmd, console)
    if isinstance(cmd, ConfigCmd):
        return _config(cmd, console)
    if isinstance(cmd, StoreCmd):
        return _store(cmd, console)
    if isinstance(cmd, HelpCmd):
        return _help(console)
    if isinstance(cmd, OpenCmd):
        return _open(cmd.kind, console)
    raise UsageError(f"unknown command: {cmd}")
