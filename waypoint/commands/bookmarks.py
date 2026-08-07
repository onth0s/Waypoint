"""Bookmark management command handlers."""

from __future__ import annotations

import os

from rich.console import Console
from rich.markup import escape
from rich.table import Column, Table

from waypoint import clipboard, store
from waypoint.constants import EXIT_ERROR, EXIT_OK, TEMP_SLOT
from waypoint.output import err, hint, ok, warn
from waypoint.prompts import prompt_name
from waypoint.resolver import AddCmd, DefaultCmd, GetCmd, RmCmd, SetCmd, looks_like_path

__all__ = ["_add", "_rm", "_ls", "_default", "_set", "_get", "_set_temp_slot"]


def _add(cmd: AddCmd, console: Console) -> int:
    explicit_alias, path_arg = cmd.alias, cmd.path
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


def _rm(cmd: RmCmd, console: Console) -> int:
    alias = cmd.alias
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


def _row_style(has_default: bool, is_cwd: bool) -> str | None:
    """Row style for a bookmark: default marker, current-dir highlight, or both."""
    if has_default and is_cwd:
        return "bold green on bright_black"
    if is_cwd:
        return "bold white on bright_black"
    if has_default:
        return "bold green"
    return None


def _ls(console: Console) -> int:
    b = store.load_bookmarks()
    if not b.bookmarks:
        hint(console, "No bookmarks yet. Add one with: [bold]wp add[/bold]")
        return EXIT_OK

    cwd = os.path.normcase(os.path.abspath(os.getcwd()))

    # Group aliases by normalized path while preserving first-seen order
    path_groups: dict[str, list[str]] = {}
    for alias, path in b.bookmarks.items():
        norm = os.path.normcase(path)
        if norm not in path_groups:
            path_groups[norm] = []
        path_groups[norm].append(alias)

    table = Table(
        Column("Alias", style="cyan"),
        Column("Path", style="bright_white", overflow="fold"),
        header_style="bold cyan",
        show_edge=True,
    )

    # Reconstruct actual path for each norm key
    path_map: dict[str, str] = {}
    for _alias, path in b.bookmarks.items():
        norm = os.path.normcase(path)
        if norm not in path_map:
            path_map[norm] = path

    for norm, aliases in path_groups.items():
        path = path_map[norm]
        has_default = any(a == b.default for a in aliases)
        is_cwd = os.path.normcase(os.path.abspath(path)) == cwd
        formatted_aliases = [
            f"{a} *" if a == b.default else a for a in aliases
        ]
        alias_str = ", ".join(formatted_aliases)
        row_style = _row_style(has_default, is_cwd)
        table.add_row(alias_str, path, style=row_style)

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


def _set_default(arg: str | None, console: Console) -> int:
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


def _default(cmd: DefaultCmd, console: Console) -> int:
    return _set_default(cmd.arg, console)


def _set(cmd: SetCmd, console: Console) -> int:
    return _set_default(cmd.arg, console)


def _get(cmd: GetCmd, console: Console) -> int:
    """Print a bookmark's path and copy it to the clipboard (default if no alias)."""
    b = store.load_bookmarks()
    if cmd.alias is not None:
        alias = cmd.alias
        target = b.bookmarks.get(alias)
        if target is None:
            raise store.BookmarkNotFoundError(alias)
    else:
        if b.default is None:
            err(console, "No default bookmark. Set one with: [bold]wp default <alias>[/bold]")
            return EXIT_ERROR
        alias = b.default
        target = b.bookmarks.get(alias)
        if target is None:
            err(console, f"Default bookmark {alias!r} no longer exists.")
            return EXIT_ERROR
    console.print(f"[bold cyan]{escape(target)}[/bold cyan]", soft_wrap=True)
    if clipboard.copy_text(target):
        hint(console, "Copied to clipboard.")
    else:
        warn(console, "Couldn't copy to clipboard.")
    return EXIT_OK
