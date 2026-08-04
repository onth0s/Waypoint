"""Configuration command handler."""

from __future__ import annotations

import os

from rich.console import Console

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.output import err, ok
from waypoint.resolver import Command

__all__ = ["_config", "_store"]


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


def _store(cmd: Command, console: Console) -> int:
    """Handle `wp store` / `wp store <alias|path>`."""
    if cmd.args[0] is None:
        console.print(f"[bold]bookmarks:[/bold] {store.bookmarks_path()}", soft_wrap=True)
        console.print(f"[bold]history:[/bold]   {store.history_path()}", soft_wrap=True)
        return EXIT_OK
    arg = cmd.args[0]
    assert arg is not None

    b = store.load_bookmarks()
    if arg in b.bookmarks:
        target_path = b.bookmarks[arg]
    elif arg == "~" or arg.startswith("~/") or arg.startswith("~\\"):
        target_path = os.path.expanduser("~")
    elif arg.strip().lower() == "null":
        store.save_config_home(None)
        ok(console, "Store home set to default (project dir)")
        return EXIT_OK
    else:
        target_path = os.path.abspath(os.path.expanduser(arg))

    if not os.path.isdir(target_path):
        err(console, f"not a directory: {target_path}")
        return EXIT_ERROR

    store.save_config_home(target_path)
    ok(console, f"Store home set to {target_path}")
    return EXIT_OK


