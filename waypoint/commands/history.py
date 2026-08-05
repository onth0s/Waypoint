"""History and undo command handlers."""

from __future__ import annotations

import os
import sys

from rich.console import Console

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK, HISTORY_PREVIEW
from waypoint.output import err, hint
from waypoint.resolver import HistoryCmd, RecordHistoryCmd, UndoCmd

__all__ = ["_undo", "_history", "_record_history_entry"]


def _record_history_entry(cmd: RecordHistoryCmd) -> int:
    """Record an origin path directly into history.yaml."""
    origin = cmd.origin
    if origin and os.path.isdir(origin):
        entries = store.load_history()
        if not entries or os.path.normcase(entries[-1]) != os.path.normcase(origin):
            store.save_history(entries + [origin])
    return EXIT_OK


def _get_live_entries(raw_entries: list[str]) -> list[tuple[int, str]]:
    """Return list of (original_raw_index, path) for existing directories."""
    return [(i, p) for i, p in enumerate(raw_entries) if os.path.isdir(p)]


def _undo(cmd: UndoCmd, console: Console) -> int:
    """Pop N navigation origins (stale entries auto-skipped) and print the target."""
    count = cmd.steps
    entries = store.load_history()
    live = _get_live_entries(entries)
    if not live or count > len(live):
        err(console, "No navigation history to undo.")
        hint(console, "Navigate somewhere with [bold]wp <alias>[/bold] first.")
        return EXIT_ERROR

    # live is ordered oldest -> newest. Undo step 1 is the last item in live.
    target_idx, target_path = live[-count]
    # Prune history up to the target entry's raw index
    store.save_history(entries[:target_idx])
    sys.stdout.write(target_path + "\n")
    return EXIT_OK


def _history(cmd: HistoryCmd, console: Console) -> int:
    """Show the undo stack, newest first (index N = `wp undo N`)."""
    raw_entries = store.load_history()
    live = _get_live_entries(raw_entries)
    if not live:
        hint(console, "No navigation history yet. Navigate with [bold]wp <alias>[/bold] first.")
        return EXIT_OK
    live_paths = [p for _, p in live]
    shown = live_paths if cmd.full else live_paths[-HISTORY_PREVIEW:]
    # Indexed lines, newest first: 1 = live_paths[-1], 2 = live_paths[-2]...
    for i, path in enumerate(reversed(shown), start=1):
        console.print(f"{i}  {path}", soft_wrap=True)
    hidden = len(live_paths) - len(shown)
    if hidden > 0:
        hint(console, f"({hidden} more; run [bold]wp h --all[/bold])")
    return EXIT_OK
