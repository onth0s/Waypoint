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
from waypoint.resolver import AddCmd, DefaultCmd, GetCmd, MvCmd, RmCmd, SetCmd, looks_like_path

__all__ = ["_add", "_rm", "_ls", "_default", "_set", "_get", "_set_temp_slot", "_mv"]


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
    if b.default is None and b._prev_default == name:
        b.default = name
        b._prev_default = None
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
        b._prev_default = alias
        b.default = None
    store.save_bookmarks(b)
    ok(console, f"Removed {alias}")
    if was_default:
        warn(console, "default bookmark removed -- run: [bold]wp default <alias>[/bold]")
    return EXIT_OK


def _mv(cmd: MvCmd, console: Console) -> int:
    alias = cmd.alias
    new_path = os.path.abspath(os.path.expanduser(cmd.new_path))
    b = store.load_bookmarks()
    if alias not in b.bookmarks:
        err(console, f"No bookmark {alias!r}.")
        return EXIT_ERROR
    if not os.path.isdir(new_path):
        err(console, f"not a directory: {new_path}")
        return EXIT_ERROR
    b.bookmarks[alias] = new_path
    store.save_bookmarks(b)
    ok(console, f"Moved {alias} -> {new_path}")
    return EXIT_OK


def _row_style(has_default: bool, is_cwd: bool, is_alive: bool = True) -> str | None:
    """Row style for a bookmark: default marker, current-dir highlight, or both."""
    if not is_alive:
        return "dim"
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
        is_alive = os.path.isdir(path)
        formatted_aliases = [
            f"{a} *" if a == b.default else a for a in aliases
        ]
        # escape(): a bracketed segment (C:\dev\[draft]\proj) otherwise matches
        # rich's tag regex and silently loses its brackets.
        alias_str = escape(", ".join(formatted_aliases))
        # "not dim" is load-bearing -- dead rows carry a "dim" base style, and an
        # inline tag only overrides the properties it names, so plain [red]
        # inherits dim and renders the marker fainter than the live path.
        safe_path = escape(path)
        marker = " [red not dim][MISSING][/red not dim]" if not is_alive else ""
        row_style = _row_style(has_default, is_cwd, is_alive)
        table.add_row(alias_str, safe_path + marker, style=row_style)

    console.print(table)
    missing_count = sum(
        1 for norm in path_groups if not os.path.isdir(path_map[norm])
    )
    if missing_count:
        warn(
            console,
            f"{missing_count} bookmark(s) point to missing paths -- "
            "use [bold]wp mv <alias> <new_path>[/bold] to repoint",
        )
    else:
        hint(console, "* = default bookmark")
    return EXIT_OK


def _set_temp_slot(target: str, b: store.Bookmarks, console: Console) -> int:
    """Point the default at a directory via the temp slot. Returns exit code."""
    if not os.path.isdir(target):
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    b.bookmarks[TEMP_SLOT] = target
    b.default = TEMP_SLOT
    b._prev_default = None
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
        b._prev_default = None
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
            err(console, "No default bookmark.")
            hint(console, "Set one with: [bold]wp default <alias>[/bold]")
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
