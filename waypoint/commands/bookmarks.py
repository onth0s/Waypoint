"""Bookmark management command handlers."""

from __future__ import annotations

import os

from rich.console import Console
from rich.table import Table

from waypoint import clipboard, store
from waypoint.constants import EXIT_ERROR, EXIT_OK, TEMP_SLOT
from waypoint.output import err, hint, ok, warn
from waypoint.prompts import prompt_name
from waypoint.resolver import Command, looks_like_path

__all__ = ["_add", "_rm", "_ls", "_default", "_set", "_set_temp_slot"]


def _add(cmd: Command, console: Console) -> int:
    explicit_alias, path_arg = cmd.args[0], cmd.args[1]
    b = store.load_bookmarks()
    if path_arg is not None:
        target = os.path.abspath(os.path.expanduser(path_arg))
    elif explicit_alias is not None:
        target = os.getcwd()
    else:
        target = clipboard.clipboard_path() or os.getcwd()
    target = os.path.abspath(os.path.expanduser(target))
    if not os.path.isdir(target):
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    name = prompt_name(b, explicit_alias, console)
    b.bookmarks[name] = target
    store.save_bookmarks(b)
    ok(console, f"Saved {name} -> {target}")
    return EXIT_OK


def _rm(cmd: Command, console: Console) -> int:
    alias = cmd.args[0]
    assert alias is not None
    b = store.load_bookmarks()
    if (
        alias not in b.bookmarks
        and alias.endswith(" *")
        and alias.removesuffix(" *") in b.bookmarks
    ):
        alias = alias.removesuffix(" *")
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
    if arg == ".":
        return _set_temp_slot(os.getcwd(), b, console)
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
        return _set_temp_slot(clipboard.clipboard_path() or os.getcwd(), b, console)
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        ok(console, f"Default is now {arg}")
        return EXIT_OK
    if looks_like_path(arg):
        return _set_temp_slot(os.path.abspath(os.path.expanduser(arg)), b, console)
    raise store.BookmarkNotFoundError(arg)
