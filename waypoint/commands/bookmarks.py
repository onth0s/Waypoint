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

__all__ = [
    "cmd_add",
    "cmd_rm",
    "cmd_mv",
    "cmd_ls",
    "cmd_default",
    "cmd_set",
    "cmd_get",
    "set_default_target",
    "row_style",
    "_add",
    "_rm",
    "_ls",
    "_default",
    "_set",
    "_get",
    "_set_temp_slot",
    "_mv",
    "_row_style",
    "_set_default",
]


def cmd_add(cmd: AddCmd, console: Console) -> int:
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
    with store.transaction():
        # Reload under lock in case another process added bookmarks
        b = store.load_bookmarks()
        b.bookmarks[name] = target
        b.restore_default_if_readded(name)
        store.save_bookmarks(b)
    ok(console, f"Saved {name} -> {target}")
    return EXIT_OK


def cmd_rm(cmd: RmCmd, console: Console) -> int:
    alias = cmd.alias
    with store.transaction():
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
        was_default = b.remove(alias)
        store.save_bookmarks(b)
    ok(console, f"Removed {alias}")
    if was_default:
        warn(console, "default bookmark removed -- run: [bold]wp default <alias>[/bold]")
    return EXIT_OK


def cmd_mv(cmd: MvCmd, console: Console) -> int:
    alias = cmd.alias
    new_path = os.path.abspath(os.path.expanduser(cmd.new_path))
    if not os.path.isdir(new_path):
        err(console, f"not a directory: {new_path}")
        return EXIT_ERROR
    with store.transaction():
        b = store.load_bookmarks()
        if alias not in b.bookmarks:
            err(console, f"No bookmark {alias!r}.")
            return EXIT_ERROR
        b.bookmarks[alias] = new_path
        store.save_bookmarks(b)
    ok(console, f"Moved {alias} -> {new_path}")
    return EXIT_OK


def row_style(has_default: bool, is_cwd: bool, is_alive: bool = True) -> str | None:
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


def cmd_ls(console: Console) -> int:
    b = store.load_bookmarks()
    if not b.bookmarks:
        hint(console, "No bookmarks yet. Add one with: [bold]wp add[/bold]")
        return EXIT_OK

    cwd = os.path.normcase(os.path.abspath(os.getcwd()))

    # Single-pass grouping: collect aliases and path info together
    # path_groups: norm_path -> {"path": display_path, "aliases": [alias, ...], "alive": is_alive}
    path_groups: dict[str, dict[str, object]] = {}
    missing_count = 0

    for alias, path in b.bookmarks.items():
        norm = os.path.normcase(path)
        if norm not in path_groups:
            is_alive = os.path.isdir(path)
            if not is_alive:
                missing_count += 1
            path_groups[norm] = {
                "path": path,
                "aliases": [alias],
                "alive": is_alive,
            }
        else:
            aliases_list = path_groups[norm]["aliases"]
            assert isinstance(aliases_list, list)
            aliases_list.append(alias)

    table = Table(
        Column("Alias", style="cyan"),
        Column("Path", style="bright_white", overflow="fold"),
        header_style="bold cyan",
        show_edge=True,
    )

    for _norm, info in path_groups.items():
        path = str(info["path"])
        aliases = info["aliases"]
        assert isinstance(aliases, list)
        is_alive = bool(info["alive"])
        has_default = any(a == b.default for a in aliases)
        is_cwd = os.path.normcase(os.path.abspath(path)) == cwd

        formatted_aliases = [
            f"{a} *" if a == b.default else a for a in aliases
        ]
        # escape(): bracketed segments otherwise match rich tag regex
        alias_str = escape(", ".join(formatted_aliases))
        safe_path = escape(path)
        marker = " [red not dim][MISSING][/red not dim]" if not is_alive else ""
        current_row_style = row_style(has_default, is_cwd, is_alive)
        table.add_row(alias_str, safe_path + marker, style=current_row_style)

    console.print(table)
    if missing_count:
        warn(
            console,
            f"{missing_count} bookmark(s) point to missing paths -- "
            "use [bold]wp mv <alias> <new_path>[/bold] to repoint",
        )
    else:
        hint(console, "* = default bookmark")
    return EXIT_OK


def set_temp_slot(target: str, b: store.Bookmarks, console: Console) -> int:
    """Point the default at a directory via the temp slot. Returns exit code."""
    if not os.path.isdir(target):
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    b.bookmarks[TEMP_SLOT] = target
    b.set_default(TEMP_SLOT)
    store.save_bookmarks(b)
    ok(console, f"Default is now {TEMP_SLOT} -> {target}")
    return EXIT_OK


def set_default_target(arg: str | None, console: Console) -> int:
    with store.transaction():
        b = store.load_bookmarks()
        if arg == ".":
            return set_temp_slot(os.getcwd(), b, console)
        if arg is None:
            return set_temp_slot(clipboard.clipboard_path() or os.getcwd(), b, console)
        if arg in b.bookmarks:
            b.set_default(arg)
            store.save_bookmarks(b)
            ok(console, f"Default is now {arg}")
            return EXIT_OK
        if looks_like_path(arg):
            return set_temp_slot(os.path.abspath(os.path.expanduser(arg)), b, console)
    raise store.BookmarkNotFoundError(arg)


def cmd_default(cmd: DefaultCmd, console: Console) -> int:
    return set_default_target(cmd.arg, console)


def cmd_set(cmd: SetCmd, console: Console) -> int:
    return set_default_target(cmd.arg, console)


def cmd_get(cmd: GetCmd, console: Console) -> int:
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


# Backward-compatibility aliases
_add = cmd_add
_rm = cmd_rm
_mv = cmd_mv
_ls = cmd_ls
_row_style = row_style
_set_temp_slot = set_temp_slot
_set_default = set_default_target
_default = cmd_default
_set = cmd_set
_get = cmd_get
