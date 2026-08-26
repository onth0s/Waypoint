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


def _help(console: Console, full: bool = False) -> int:
    if full:
        console.print("[bold cyan]Waypoint[/bold cyan] -- path bookmark CLI (Full Reference)")
        console.print()
        console.print("[bold cyan]Navigate[/bold cyan]")
        console.print("  [cyan]wp[/cyan]                     go to default bookmark")
        console.print("  [cyan]wp <alias>[/cyan]             go to bookmark named <alias>")
        console.print(
            "  [cyan]wp undo \\[N][/cyan]            go to history row N "
            "(default 1 = last jump, 0 = current dir)"
        )
        console.print("  [cyan]wp u \\[N][/cyan]               alias for wp undo \\[N]")
        console.print(
            "  [cyan]wp U, wp uu[/cyan]            shortcuts for wp undo 0 "
            "(re-land on current dir)"
        )
        console.print(
            f"  [cyan]wp history \\[N][/cyan]         show newest N history rows "
            f"(default {HISTORY_PREVIEW}; row 0 = current dir)"
        )
        console.print("  [cyan]wp h \\[N][/cyan]               alias for wp history \\[N]")
        console.print(
            "  [cyan]wp history --all[/cyan]       "
            "show full navigation history stack (up to 50 entries)"
        )
        console.print(
            "                         (flags: --all, --full, all, full, a, f)"
        )
        console.print()
        console.print("[bold cyan]Manage Bookmarks[/bold cyan]")
        console.print(
            "  [cyan]wp add[/cyan]                 bookmark current dir (prompts for alias)"
        )
        console.print("  [cyan]wp add <alias>[/cyan]         bookmark current dir as <alias>")
        console.print("  [cyan]wp add <alias> <path>[/cyan]  bookmark <path> as <alias>")
        console.print(
            "  [cyan]wp add .[/cyan]               "
            "shorthand to bookmark current dir (prompts for alias)"
        )
        console.print("  [cyan]wp rm <alias>[/cyan]          delete a bookmark")
        console.print("  [cyan]wp mv <alias> <path>[/cyan]  repoint <alias> to a new directory")
        console.print(
            "  [cyan]wp ls, wp list[/cyan]         "
            "list all bookmarks (shows default * and highlights cwd)"
        )
        console.print(
            "  [cyan]wp get \\[alias][/cyan]         print bookmark path and copy to clipboard "
            "(default if omitted)"
        )
        console.print(
            "  [cyan]wp set \\[alias|path|~][/cyan]  set default (clipboard -> cwd -> temp slot)"
        )
        console.print("  [cyan]wp default <alias>[/cyan]     set default bookmark to <alias>")
        console.print(
            "  [cyan]wp default . | <path|~>[/cyan] "
            "point default at a directory or home (temp slot)"
        )
        console.print()
        console.print("[bold cyan]External Launchers[/bold cyan]")
        console.print("  [cyan]wp .[/cyan]                   open default bookmark in Explorer")
        console.print("  [cyan]wp -vs[/cyan]                 open default bookmark in VS Code")
        console.print()
        console.print("[bold cyan]Settings & Storage Commands[/bold cyan]")
        console.print(
            "  [cyan]wp store[/cyan]               "
            "show active waypoint.yaml and history.yaml locations"
        )
        console.print(
            "  [cyan]wp store <alias|path|~>[/cyan] "
            "set bookmark storage directory (creates if missing)"
        )
        console.print("  [cyan]wp config[/cyan]              show configured storage home")
        console.print(
            "  [cyan]wp config home <path>[/cyan]  set persistent storage home directory"
        )
        console.print(
            "  [cyan]wp config home null[/cyan]    reset persistent storage home to default"
        )
        console.print()
        console.print("[bold cyan]Data File Specs & Hierarchies[/bold cyan]")
        console.print("  [cyan]1. waypoint.yaml[/cyan] (Bookmarks & Default)")
        console.print("     Schema:")
        console.print("       bookmarks:")
        console.print("         <alias>: \"<directory_path>\"")
        console.print("       default: <alias_name_or_temp>")
        console.print(
            "     Notes: Stores named paths and default target. Auto-seeded on first run."
        )
        console.print()
        console.print("  [cyan]2. history.yaml[/cyan] (Navigation Stack)")
        console.print("     Schema:")
        console.print("       - \"<oldest_directory_path>\"")
        console.print("       - ...")
        console.print("       - \"<newest_directory_path>\"")
        console.print("     Notes: Stack of visited directories (newest at bottom, row 0).")
        console.print("            Auto-deduped and capped to 50 entries (UNDO_STACK).")
        console.print()
        console.print("  [cyan]3. config.yaml[/cyan] (Global Settings in Project Dir)")
        console.print("     Schema:")
        console.print("       home: null | \"<custom_data_directory_path>\"")
        console.print("     Notes: Sets global fallback folder for waypoint.yaml and history.yaml.")
        console.print()
        console.print("[bold cyan]Data Resolution Order (Highest to Lowest Precedence)[/bold cyan]")
        console.print("  1. CWD: waypoint.yaml / history.yaml in current working directory")
        console.print("  2. WP_HOME: environment variable (if non-empty)")
        console.print("  3. config.yaml: `home` setting (if non-null)")
        console.print("  4. Default: ~/.waypoint (user profile directory)")
        console.print("  (Note: CWD resolution is evaluated independently per file)")
        console.print()
        console.print("[bold cyan]Shell Protocol Contract[/bold cyan]")
        console.print(
            "  - Bare directory paths on stdout trigger `Set-Location` in the shell wrapper."
        )
        console.print(
            "  - All other output is styled rich text and does not trigger directory moves."
        )
        console.print(
            "  - Interactive commands (e.g. `wp add`) run live to prevent prompt buffering."
        )
        console.print()
        console.print("[bold cyan]Help[/bold cyan]")
        console.print("  [cyan]wp help, wp --help, -h, -?[/cyan]  show usage summary")
        console.print("  [cyan]wp --help-full, wp help -f[/cyan]  show this full reference")
        return EXIT_OK

    console.print("[bold cyan]Waypoint[/bold cyan] -- path bookmark CLI")
    console.print()
    console.print("[bold cyan]Navigate[/bold cyan]")
    console.print("  [cyan]wp[/cyan]                          go to default bookmark")
    console.print("  [cyan]wp <alias>[/cyan]                  go to bookmark named <alias>")
    console.print(
        "  [cyan]wp undo \\[N][/cyan]                 go to history row N "
        "(0 = current, 1 = last jump; wp u, wp U)"
    )
    console.print(
        f"  [cyan]wp history \\[N][/cyan]              show last {HISTORY_PREVIEW} dirs "
        "(wp h, wp h --all)"
    )
    console.print()
    console.print("[bold cyan]Manage[/bold cyan]")
    console.print(
        "  [cyan]wp add \\[alias] \\[path][/cyan]       bookmark a dir "
        "(prompts if omitted, '.' for cwd)"
    )
    console.print("  [cyan]wp rm <alias>[/cyan]               delete a bookmark")
    console.print("  [cyan]wp mv <alias> <path>[/cyan]       repoint <alias> to a new directory")
    console.print("  [cyan]wp ls, wp list[/cyan]              list all bookmarks")
    console.print(
        "  [cyan]wp set \\[alias|path|~][/cyan]       set default (clipboard -> cwd -> temp)"
    )
    console.print(
        "  [cyan]wp get \\[alias][/cyan]              copy a bookmark's path to the clipboard"
    )
    console.print("  [cyan]wp default <alias>[/cyan]          set the default bookmark")
    console.print("  [cyan]wp default . | <path|~>[/cyan]     point default at a dir (temp slot)")
    console.print()
    console.print("[bold cyan]Open[/bold cyan]")
    console.print("  [cyan]wp .[/cyan]                        open default bookmark in Explorer")
    console.print("  [cyan]wp -vs[/cyan]                      open default bookmark in VS Code")
    console.print()
    console.print("[bold cyan]Settings[/bold cyan]")
    console.print("  [cyan]wp store \\[alias|path|~][/cyan]     show or set data storage directory")
    console.print("  [cyan]wp config \\[home <path>][/cyan]    show or set configured store home")
    console.print()
    console.print("[bold cyan]Help[/bold cyan]")
    console.print("  [cyan]wp help, wp --help, -h, -?[/cyan]  show this usage")
    console.print(
        "  [cyan]wp --help-full[/cyan]              show full reference "
        "(aliases, flags, resolution rules)"
    )
    return EXIT_OK
