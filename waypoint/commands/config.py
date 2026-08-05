"""Configuration command handler."""

from __future__ import annotations

import os

from rich.console import Console

from waypoint import store
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.output import err, ok
from waypoint.resolver import ConfigCmd, StoreCmd

__all__ = ["_config", "_store"]


def _config(cmd: ConfigCmd, console: Console) -> int:
    if cmd.target is None:
        # Labeled line, never a bare path: the wrapper's cd discriminator must
        # not mistake this for a navigation target. soft_wrap keeps the long
        # path on one line instead of wrapping it onto a bare-path-looking line.
        console.print(f"home: {store.data_dir()}", soft_wrap=True)
        return EXIT_OK
    target = cmd.target
    if target.strip().lower() == "null":
        # Documented default (config.yaml: `home: null` = project dir).
        store.save_config_home(None)
        ok(console, "Home set to default (project dir)")
        return EXIT_OK
    target = os.path.abspath(os.path.expanduser(target))
    store.save_config_home(target)
    ok(console, f"Home set to {target}")
    return EXIT_OK


def _store(cmd: StoreCmd, console: Console) -> int:
    """Handle `wp store` / `wp store <alias|path>`."""
    if cmd.arg is None:
        b_path, h_path = store.bookmarks_path(), store.history_path()
        console.print(f"[bold cyan]bookmarks:[/bold cyan] [cyan]{b_path}[/cyan]", soft_wrap=True)
        console.print(
            f"[bold magenta]history:[/bold magenta]   [magenta]{h_path}[/magenta]",
            soft_wrap=True,
        )
        return EXIT_OK
    arg = cmd.arg

    b = store.load_bookmarks()
    if arg in b.bookmarks:
        target_path = b.bookmarks[arg]
    elif arg.startswith("~"):
        target_path = os.path.expanduser(arg)
    elif arg.strip().lower() == "null":
        store.save_config_home(None)
        ok(console, "Store home set to default (project dir)")
        return EXIT_OK
    else:
        target_path = os.path.abspath(os.path.expanduser(arg))

    try:
        os.makedirs(target_path, exist_ok=True)
    except OSError as e:
        err(console, f"cannot create directory {target_path}: {e}")
        return EXIT_ERROR

    store.save_config_home(target_path)
    ok(console, f"Store home set to {target_path}")
    return EXIT_OK
