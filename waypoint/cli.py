"""Waypoint CLI: dispatch and entry point.

Stdout protocol (load-bearing, consumed by the `wp` PowerShell wrapper in
install.ps1): a navigation invocation prints ONLY the resolved absolute path
to stdout and exits 0 -- the wrapper cds when stdout is exactly one line that
is an existing path. Everything else is human output rendered via rich on
stdout (never stderr, since PowerShell shows native stderr as red error
records). The bare nav path is the single sanctioned exception to AGENTS.md's
"use rich for all output" rule: it is machine protocol, not text for a human.
"""

from __future__ import annotations

import os
import sys

from rich.console import Console

from waypoint.commands.bookmarks import (
    cmd_add,
    cmd_default,
    cmd_get,
    cmd_ls,
    cmd_mv,
    cmd_rm,
    cmd_set,
)
from waypoint.commands.config import cmd_config, cmd_store
from waypoint.commands.history import cmd_history, cmd_record_history, cmd_undo
from waypoint.commands.launcher import cmd_help, cmd_open
from waypoint.commands.nav import cmd_nav
from waypoint.constants import EXIT_ERROR, EXIT_USAGE, WaypointError
from waypoint.output import err, hint
from waypoint.prompts import PromptCancelled
from waypoint.resolver import (
    AddCmd,
    Command,
    ConfigCmd,
    DefaultCmd,
    GetCmd,
    HelpCmd,
    HistoryCmd,
    LsCmd,
    MvCmd,
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
        # no-op on pipes (the wrapper captures stdout) -- force ANSI writes.
        legacy_windows=False if force else None,
        # Default highlight bolds every balanced "(...)" via ReprHighlighter,
        # injecting escape codes mid-text -- noise for end users and it can make
        # a single rich line trip the wrapper's Test-Path. Off.
        highlight=False,
    )
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        cmd = parse_args(args)
        return dispatch(cmd, console)
    except PromptCancelled:
        console.print("[yellow]Cancelled.[/yellow]")
        return EXIT_ERROR
    except UsageError as e:
        err(console, e)
        hint(console, "Run [bold]wp help[/bold] for usage.")
        return EXIT_USAGE
    except WaypointError as e:
        err(console, e)
        return e.exit_code


def dispatch(cmd: Command, console: Console) -> int:
    """Route a parsed command to its handler."""
    if isinstance(cmd, RecordHistoryCmd):
        return cmd_record_history(cmd)
    if isinstance(cmd, NavCmd):
        return cmd_nav(cmd, console)
    if isinstance(cmd, UndoCmd):
        return cmd_undo(cmd, console)
    if isinstance(cmd, HistoryCmd):
        return cmd_history(cmd, console)
    if isinstance(cmd, AddCmd):
        return cmd_add(cmd, console)
    if isinstance(cmd, RmCmd):
        return cmd_rm(cmd, console)
    if isinstance(cmd, MvCmd):
        return cmd_mv(cmd, console)
    if isinstance(cmd, LsCmd):
        return cmd_ls(console)
    if isinstance(cmd, DefaultCmd):
        return cmd_default(cmd, console)
    if isinstance(cmd, SetCmd):
        return cmd_set(cmd, console)
    if isinstance(cmd, GetCmd):
        return cmd_get(cmd, console)
    if isinstance(cmd, ConfigCmd):
        return cmd_config(cmd, console)
    if isinstance(cmd, StoreCmd):
        return cmd_store(cmd, console)
    if isinstance(cmd, HelpCmd):
        return cmd_help(console, full=cmd.full)
    if isinstance(cmd, OpenCmd):
        return cmd_open(cmd.kind, console)
    raise UsageError(f"unknown command: {cmd}")
