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
    except OSError:
        err(console, f"{app} not found on PATH.")
        return EXIT_ERROR
    console.print(f"[cyan]Opening[/cyan] {target} in {app}", soft_wrap=True)
    return EXIT_OK


def _help(console: Console) -> int:
    console.print("[bold cyan]Waypoint[/bold cyan] -- path bookmark CLI")
    console.print()
    console.print("[bold cyan]Navigate[/bold cyan]")
    console.print("  [cyan]wp[/cyan]                  go to default bookmark")
    console.print("  [cyan]wp <alias>[/cyan]          go to bookmark named <alias>")
    console.print("  [cyan]wp undo \\[N][/cyan]         go to history row N (0 = current; wp u)")
    console.print(f"  [cyan]wp history \\[N][/cyan]      show last {HISTORY_PREVIEW} dirs (wp h)")
    console.print("  [cyan]wp history --all[/cyan]    show full navigation history (wp h --all)")
    console.print()
    console.print("[bold cyan]Manage[/bold cyan]")
    console.print("  [cyan]wp add \\[alias] \\[path][/cyan] bookmark a dir (prompts if omitted)")
    console.print("  [cyan]wp rm <alias>[/cyan]           delete a bookmark")
    console.print("  [cyan]wp ls, wp list[/cyan]          list all bookmarks")
    console.print("  [cyan]wp set \\[alias|path|~][/cyan] set default (clipboard -> cwd -> temp)")
    console.print("  [cyan]wp get \\[alias][/cyan]        copy a bookmark's path to the clipboard")
    console.print("  [cyan]wp default <alias>[/cyan]    set the default bookmark")
    console.print("  [cyan]wp default . | <path|~>[/cyan] point default at a dir (temp slot)")
    console.print()
    console.print("[bold cyan]Open[/bold cyan]")
    console.print("  [cyan]wp .[/cyan]                   open default bookmark in Explorer")
    console.print("  [cyan]wp -vs[/cyan]                 open default bookmark in VS Code")
    console.print()
    console.print("[bold cyan]Settings[/bold cyan]")
    console.print("  [cyan]wp config[/cyan]              show where waypoint.yaml lives")
    console.print("  [cyan]wp config home <path>[/cyan]  set where waypoint.yaml lives")
    console.print()
    console.print("[bold cyan]Help[/bold cyan]")
    console.print("  [cyan]wp help, wp -h, wp -?[/cyan]  show this usage")
    return EXIT_OK
