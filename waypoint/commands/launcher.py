"""External app launcher and help command handlers."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console

from waypoint import store
from waypoint.commands.nav import _default_target, _require_dir
from waypoint.constants import EXIT_ERROR, EXIT_OK, HISTORY_PREVIEW
from waypoint.output import err

__all__ = ["_open", "_help"]


def _open(kind: str, console: Console) -> int:
    b = store.load_bookmarks()
    target = _default_target(b, console)
    if target is None or b.default is None:
        return EXIT_ERROR
    if not _require_dir(target, b.default, console):
        return EXIT_ERROR
    app = "Explorer" if kind == "explorer" else "VS Code"
    exe = "explorer" if kind == "explorer" else "code"
    resolved = shutil.which(exe)
    if resolved is None:
        err(console, f"{app} not found on PATH.")
        return EXIT_ERROR
    try:
        if resolved.lower().endswith((".cmd", ".bat")):
            subprocess.Popen(["cmd", "/c", resolved, target])
        else:
            subprocess.Popen([resolved, target])
    except FileNotFoundError:
        err(console, f"{app} not found on PATH.")
        return EXIT_ERROR
    console.print(f"[cyan]Opening[/cyan] {target} in {app}", soft_wrap=True)
    return EXIT_OK


def _help(console: Console) -> int:
    console.print("[bold]Waypoint[/bold] -- path bookmark CLI")
    console.print()
    console.print("[bold]Navigate[/bold]")
    console.print("  wp                  go to default bookmark")
    console.print("  wp <alias>          go to bookmark named <alias>")
    console.print("  wp undo [N]         go back N navigation steps (wp u)")
    console.print(f"  wp history          show last {HISTORY_PREVIEW} navigation steps (wp h)")
    console.print("  wp history --all    show the full navigation history (wp h --all)")
    console.print()
    console.print("[bold]Manage[/bold]")
    console.print("  wp add [alias] [path]   bookmark a directory (prompts for name if omitted)")
    console.print("  wp rm <alias>           delete a bookmark")
    console.print("  wp ls, wp list          list all bookmarks")
    console.print("  wp set [alias|path]   set the default (clipboard -> cwd -> temp slot)")
    console.print("  wp default <alias>      set the default bookmark")
    console.print("  wp default . | <path>   point default at a directory (temp slot)")
    console.print()
    console.print("[bold]Open[/bold]")
    console.print("  wp .                   open default bookmark in Explorer")
    console.print("  wp -vs                 open default bookmark in VS Code")
    console.print()
    console.print("[bold]Settings[/bold]")
    console.print("  wp config              show where waypoint.yaml lives")
    console.print("  wp config home <path>  set where waypoint.yaml lives")
    console.print()
    console.print("[bold]Help[/bold]")
    console.print("  wp help, wp -h, wp -?  show this usage")
    return EXIT_OK
