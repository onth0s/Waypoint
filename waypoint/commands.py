"""Command handlers for the Waypoint CLI.

Each function takes (cmd, console) and returns an exit code.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pyperclip
from rich.console import Console
from rich.table import Table

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK, TEMP_SLOT
from waypoint.output import err, hint, ok, warn
from waypoint.prompts import prompt_name
from waypoint.resolver import Command, looks_like_path

# --- navigation -------------------------------------------------------------


def _nav(cmd: Command, console: Console) -> int:
    b = store.load_bookmarks()
    if cmd.args:
        alias = cmd.args[0]
        assert alias is not None  # parse_args always fills nav args with a str
        target = b.bookmarks.get(alias)
        if target is None:
            err(console, f"No bookmark {alias!r}.")
            hint(console, "Run [bold]wp ls[/bold] to see bookmarks.")
            return EXIT_ERROR
        if not _require_dir(target, alias, console):
            return EXIT_ERROR
    else:
        target = _default_target(b, console)
        if target is None:
            return EXIT_ERROR
        assert b.default is not None  # _default_target only returns a target when one exists
        if not _require_dir(target, b.default, console):
            return EXIT_ERROR
    sys.stdout.write(target + "\n")
    return EXIT_OK


def _default_target(b: store.Bookmarks, console: Console) -> str | None:
    """Resolve the default bookmark's path; print an error and return None on failure."""
    if b.default is None:
        err(console, "No default bookmark. Set one with: [bold]wp default <alias>[/bold]")
        return None
    target = b.bookmarks.get(b.default)
    if target is None:
        err(console, f"Default bookmark {b.default!r} no longer exists.")
        return None
    return target


def _require_dir(target: str, label: str, console: Console) -> bool:
    if not os.path.isdir(target):
        err(console, f"Bookmark {label!r} points to a path that doesn't exist: {target}")
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
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    name = prompt_name(b, explicit_alias, console)
    b.bookmarks[name] = target
    store.save_bookmarks(b)
    ok(console, f"Saved {name} -> {target}")
    return EXIT_OK


def clipboard_path() -> str | None:
    """Clipboard text if it is an existing path (paste from Explorer), else None."""
    try:
        raw = pyperclip.paste()
    except (OSError, RuntimeError):
        return None
    if not raw:
        return None
    text: str = raw.strip().strip('"')
    if os.path.isdir(text):
        return text
    if os.path.isfile(text):
        return os.path.dirname(text)
    return None


def _rm(cmd: Command, console: Console) -> int:
    alias = cmd.args[0]
    b = store.load_bookmarks()
    if alias not in b.bookmarks:
        err(console, f"No bookmark {alias!r}.")
        return EXIT_ERROR
    was_default = b.default == alias
    del b.bookmarks[alias]
    if was_default:
        b.default = None
    store.save_bookmarks(b)
    ok(console, f"Removed {alias}")
    if was_default:
        warn(console, "default bookmark removed -- run: [bold]wp default <alias>[/bold]")
    return EXIT_OK


def _ls(console: Console) -> int:
    b = store.load_bookmarks()
    if not b.bookmarks:
        hint(console, "No bookmarks yet. Add one with: [bold]wp add[/bold]")
        return EXIT_OK
    table = Table("Alias", "Path")
    for alias, path in b.bookmarks.items():
        label = f"{alias} *" if alias == b.default else alias
        table.add_row(label, path, style="bold" if alias == b.default else None)
    console.print(table)
    hint(console, "* = default bookmark")
    return EXIT_OK


def _set_temp_slot(target: str, b: store.Bookmarks, console: Console) -> int:
    """Point the default at a directory via the temp slot. Returns exit code."""
    if not os.path.isdir(target):
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    b.bookmarks[TEMP_SLOT] = target
    b.default = TEMP_SLOT
    store.save_bookmarks(b)
    ok(console, f"Default is now {TEMP_SLOT} -> {target}")
    return EXIT_OK


def _default(cmd: Command, console: Console) -> int:
    arg = cmd.args[0]
    assert arg is not None  # parse_args requires exactly one arg for default
    b = store.load_bookmarks()
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        ok(console, f"Default is now {arg}")
        return EXIT_OK
    if looks_like_path(arg):
        return _set_temp_slot(os.path.abspath(os.path.expanduser(arg)), b, console)
    raise store.BookmarkNotFoundError(arg)


def _set(cmd: Command, console: Console) -> int:
    arg = cmd.args[0]
    b = store.load_bookmarks()
    if arg == ".":
        return _set_temp_slot(os.getcwd(), b, console)
    if arg is None:
        return _set_temp_slot(clipboard_path() or os.getcwd(), b, console)
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        ok(console, f"Default is now {arg}")
        return EXIT_OK
    if looks_like_path(arg):
        return _set_temp_slot(os.path.abspath(os.path.expanduser(arg)), b, console)
    raise store.BookmarkNotFoundError(arg)


# --- settings ---------------------------------------------------------------


def _config(cmd: Command, console: Console) -> int:
    if cmd.args[0] is None:
        # Labeled line, never a bare path: the wrapper's cd discriminator must
        # not mistake this for a navigation target. soft_wrap keeps the long
        # path on one line instead of wrapping it onto a bare-path-looking line.
        console.print(f"home: {store.data_dir()}", soft_wrap=True)
        return EXIT_OK
    target = cmd.args[1]
    assert target is not None  # args[0] non-None implies a (key, value) pair
    if target.strip().lower() == "null":
        # Documented default (config.yaml: `home: null` = project dir).
        store.save_config_home(None)
        ok(console, "Home set to default (project dir)")
        return EXIT_OK
    target = os.path.abspath(os.path.expanduser(target))
    store.save_config_home(target)
    ok(console, f"Home set to {target}")
    return EXIT_OK


# --- open locations ---------------------------------------------------------


def _open(kind: str, console: Console) -> int:
    b = store.load_bookmarks()
    target = _default_target(b, console)
    if target is None:
        return EXIT_ERROR
    assert b.default is not None  # _default_target only returns a target when one exists
    if not _require_dir(target, b.default, console):
        return EXIT_ERROR
    app = "Explorer" if kind == "explorer" else "VS Code"
    exe = "explorer" if kind == "explorer" else "code"
    try:
        subprocess.Popen([exe, target])
    except FileNotFoundError:
        err(console, f"{app} not found on PATH.")
        return EXIT_ERROR
    console.print(f"[cyan]Opening[/cyan] {target} in {app}")
    return EXIT_OK


# --- help -------------------------------------------------------------------


def _help(console: Console) -> int:
    console.print("[bold]Waypoint[/bold] -- path bookmark CLI")
    console.print()
    console.print("[bold]Navigate[/bold]")
    console.print("  wp                  go to default bookmark")
    console.print("  wp <alias>          go to bookmark named <alias>")
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
