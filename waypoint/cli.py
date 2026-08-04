"""Waypoint CLI: dispatch and end-user output.

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
import subprocess
import sys

import pyperclip
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from waypoint import store
from waypoint.resolver import Command, UsageError, looks_like_path, parse_args, validate_alias


class _Cancelled(Exception):
    """Interactive prompt aborted by the user (EOF / Ctrl+C / 'cancel')."""


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
    except UsageError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("Run [bold]wp help[/bold] for usage.")
        return 2
    try:
        return dispatch(cmd, console)
    except _Cancelled:
        console.print("Cancelled.")
        return 1
    except UsageError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print("Run [bold]wp help[/bold] for usage.")
        return 2
    except store.StoreError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1


def dispatch(cmd: Command, console: Console) -> int:
    if cmd.kind == "nav":
        return _nav(cmd, console)
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
    if cmd.kind == "help":
        return _help(console)
    if cmd.kind in ("explorer", "code"):
        return _open(cmd.kind, console)
    raise UsageError(f"unknown command: {cmd.kind}")  # unreachable


# --- navigation -------------------------------------------------------------


def _nav(cmd: Command, console: Console) -> int:
    b = store.load_bookmarks()
    if cmd.args:
        alias = cmd.args[0]
        target = b.bookmarks.get(alias)
        if target is None:
            console.print(f"[bold red]Error:[/bold red] No bookmark {alias!r}.")
            console.print("Run [bold]wp ls[/bold] to see bookmarks.")
            return 1
        if not _require_dir(target, alias, console):
            return 1
    else:
        target = _default_target(b, console)
        if target is None:
            return 1
        if not _require_dir(target, b.default, console):
            return 1
    sys.stdout.write(target + "\n")
    return 0


def _default_target(b: store.Bookmarks, console: Console) -> str | None:
    """Resolve the default bookmark's path; print an error and return None on failure."""
    if b.default is None:
        console.print(
            "[bold red]Error:[/bold red] No default bookmark. Set one with: "
            "[bold]wp default <alias>[/bold]"
        )
        return None
    target = b.bookmarks.get(b.default)
    if target is None:
        console.print(
            f"[bold red]Error:[/bold red] Default bookmark {b.default!r} no longer exists."
        )
        return None
    return target


def _require_dir(target: str, label: str, console: Console) -> bool:
    if not os.path.isdir(target):
        console.print(
            f"[bold red]Error:[/bold red] Bookmark {label!r} points to a path "
            f"that doesn't exist: {target}"
        )
        return False
    return True


# --- manage bookmarks -------------------------------------------------------


def _add(cmd: Command, console: Console) -> int:
    explicit_alias, path_arg = cmd.args[0], cmd.args[1]
    b = store.load_bookmarks()
    if path_arg is not None:
        target = os.path.abspath(os.path.expanduser(path_arg))
    else:
        target = clipboard_path() or os.getcwd()
    target = os.path.abspath(os.path.expanduser(target))
    if not os.path.isdir(target):
        console.print(f"[bold red]Error:[/bold red] not a directory: {target}")
        return 1
    name = _prompt_name(b, explicit_alias, console)
    b.bookmarks[name] = target
    store.save_bookmarks(b)
    console.print(f"[bold green]Saved[/bold green] {name} → {target}")
    return 0


def clipboard_path() -> str | None:
    """Clipboard text if it is an existing path (paste from Explorer), else None."""
    try:
        text = pyperclip.paste()
    except Exception:
        return None
    if not text:
        return None
    text = text.strip().strip('"')
    if os.path.isdir(text):
        return text
    if os.path.isfile(text):
        return os.path.dirname(text)
    return None


def _prompt_name(b: store.Bookmarks, explicit: str | None, console: Console) -> str:
    """Return a valid, non-colliding bookmark name; prompt when the alias is absent."""
    name = explicit
    while True:
        if name is None:
            try:
                name = Prompt.ask("[bold]Bookmark name[/bold]")
            except (EOFError, KeyboardInterrupt):
                raise _Cancelled from None
        try:
            validate_alias(name)
        except UsageError:
            if explicit is not None:
                raise  # bad explicit alias -> usage error, exit 2
            console.print(f"[bold red]Error:[/bold red] {name!r} is not a valid bookmark name.")
            name = None
            continue
        if name in b.bookmarks:
            try:
                choice = Prompt.ask(
                    f"Bookmark {name!r} already exists — override, rename, or cancel?",
                    choices=["override", "rename", "cancel"],
                )
            except (EOFError, KeyboardInterrupt):
                raise _Cancelled from None
            if choice == "cancel":
                raise _Cancelled
            if choice == "rename":
                name = None
                continue
            # "override": fall through with the same name
        return name


def _rm(cmd: Command, console: Console) -> int:
    alias = cmd.args[0]
    b = store.load_bookmarks()
    if alias not in b.bookmarks:
        console.print(f"[bold red]Error:[/bold red] No bookmark {alias!r}.")
        return 1
    was_default = b.default == alias
    del b.bookmarks[alias]
    if was_default:
        b.default = None
    store.save_bookmarks(b)
    console.print(f"[bold green]Removed[/bold green] {alias}")
    if was_default:
        console.print(
            "[yellow]Warning:[/yellow] default bookmark removed — run: "
            "[bold]wp default <alias>[/bold]"
        )
    return 0


def _ls(console: Console) -> int:
    b = store.load_bookmarks()
    if not b.bookmarks:
        console.print("No bookmarks yet. Add one with: [bold]wp add[/bold]")
        return 0
    table = Table("Alias", "Path")
    for alias, path in b.bookmarks.items():
        label = f"{alias} *" if alias == b.default else alias
        table.add_row(label, path, style="bold" if alias == b.default else None)
    console.print(table)
    console.print("* = default bookmark")
    return 0


def _default(cmd: Command, console: Console) -> int:
    arg = cmd.args[0]
    b = store.load_bookmarks()
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] {arg}")
        return 0
    if looks_like_path(arg):
        # Path form: point the default at a directory directly, via the `temp`
        # slot bookmark — zzcd-style single-slot "current dir" memory.
        target = os.path.abspath(os.path.expanduser(arg))
        if not os.path.isdir(target):
            console.print(f"[bold red]Error:[/bold red] not a directory: {target}")
            return 1
        b.bookmarks["temp"] = target
        b.default = "temp"
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] temp → {target}")
        return 0
    console.print(f"[bold red]Error:[/bold red] No bookmark {arg!r}.")
    return 1


def _set(cmd: Command, console: Console) -> int:
    arg = cmd.args[0]
    b = store.load_bookmarks()
    # Dot: cwd only, skip clipboard.
    if arg == ".":
        target = os.getcwd()
        target = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(target):
            console.print(f"[bold red]Error:[/bold red] not a directory: {target}")
            return 1
        b.bookmarks["temp"] = target
        b.default = "temp"
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] temp -> {target}")
        return 0
    # No arg: clipboard first, then cwd.
    if arg is None:
        target = clipboard_path() or os.getcwd()
        target = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(target):
            console.print(f"[bold red]Error:[/bold red] not a directory: {target}")
            return 1
        b.bookmarks["temp"] = target
        b.default = "temp"
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] temp -> {target}")
        return 0
    # Alias form: set default to an existing bookmark.
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] {arg}")
        return 0
    # Path form: point default at a directory directly.
    if looks_like_path(arg):
        target = os.path.abspath(os.path.expanduser(arg))
        if not os.path.isdir(target):
            console.print(f"[bold red]Error:[/bold red] not a directory: {target}")
            return 1
        b.bookmarks["temp"] = target
        b.default = "temp"
        store.save_bookmarks(b)
        console.print(f"[bold green]Default is now[/bold green] temp -> {target}")
        return 0
    console.print(f"[bold red]Error:[/bold red] No bookmark {arg!r}.")
    return 1


# --- settings ---------------------------------------------------------------
def _config(cmd: Command, console: Console) -> int:
    if cmd.args[0] is None:
        # Labeled line, never a bare path: the wrapper's cd discriminator must
        # not mistake this for a navigation target. soft_wrap keeps the long
        # path on one line instead of wrapping it onto a bare-path-looking line.
        console.print(f"home: {store.data_dir()}", soft_wrap=True)
        return 0
    target = cmd.args[1]
    if target.strip().lower() == "null":
        # Documented default (config.yaml: `home: null` = project dir).
        store.save_config_home(None)
        console.print("[bold green]Home set to[/bold green] default (project dir)")
        return 0
    target = os.path.abspath(os.path.expanduser(target))
    store.save_config_home(target)
    console.print(f"[bold green]Home set to[/bold green] {target}")
    return 0


# --- open locations ---------------------------------------------------------


def _open(kind: str, console: Console) -> int:
    b = store.load_bookmarks()
    target = _default_target(b, console)
    if target is None:
        return 1
    if not _require_dir(target, b.default, console):
        return 1
    exe = "explorer" if kind == "explorer" else "code"
    try:
        subprocess.Popen([exe, target])
    except FileNotFoundError:
        app = "Explorer" if kind == "explorer" else "VS Code"
        console.print(f"[bold red]Error:[/bold red] {app} not found on PATH.")
        return 1
    app = "Explorer" if kind == "explorer" else "VS Code"
    console.print(f"[cyan]Opening[/cyan] {target} in {app}")
    return 0


# --- help -------------------------------------------------------------------


def _help(console: Console) -> int:
    console.print("[bold]Waypoint[/bold] — path bookmark CLI")
    console.print()
    console.print("[bold]Navigate[/bold]")
    console.print("  wp                  go to default bookmark")
    console.print("  wp <alias>          go to bookmark named <alias>")
    console.print()
    console.print("[bold]Manage[/bold]")
    console.print("  wp add [alias] [path]   bookmark a directory (prompts for name if omitted)")
    console.print("  wp rm <alias>           delete a bookmark")
    console.print("  wp ls                   list all bookmarks")
    console.print("  wp set [alias|path]     set the default (clipboard -> cwd -> temp slot)")
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
    return 0
