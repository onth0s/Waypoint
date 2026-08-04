"""History and undo command handlers."""

from __future__ import annotations

import os
import sys

from rich.console import Console

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK, HISTORY_PREVIEW
from waypoint.output import err, hint
from waypoint.resolver import Command

__all__ = ["_undo", "_history"]


def _undo(cmd: Command, console: Console) -> int:
    """Pop N navigation origins (stale entries auto-skipped) and print the target."""
    count = 1 if cmd.args[0] is None else int(cmd.args[0])
    entries = store.load_history()
    found = 0
    for i in range(len(entries) - 1, -1, -1):
        if not os.path.isdir(entries[i]):
            continue
        found += 1
        if found == count:
            target = entries[i]
            store.save_history(entries[:i])
            sys.stdout.write(target + "\n")
            return EXIT_OK
    err(console, "No navigation history to undo.")
    hint(console, "Navigate somewhere with [bold]wp <alias>[/bold] first.")
    return EXIT_ERROR


def _history(cmd: Command, console: Console) -> int:
    """Show the undo stack, newest first (index N = `wp undo N`)."""
    entries = store.load_history()
    if not entries:
        hint(console, "No navigation history yet. Navigate with [bold]wp <alias>[/bold] first.")
        return EXIT_OK
    shown = entries if cmd.args[0] == "all" else entries[-HISTORY_PREVIEW:]
    # Indexed lines, not a Table: full paths must survive the 80-col pipe and
    # rich cell truncation, and a prefixed line can never trip the cd gate.
    for i, path in enumerate(reversed(shown), start=1):
        console.print(f"{i}  {path}", soft_wrap=True)
    hidden = len(entries) - len(shown)
    if hidden > 0:
        hint(console, f"({hidden} more; run [bold]wp h --all[/bold])")
    return EXIT_OK
