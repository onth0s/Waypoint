"""Interactive prompts for the Waypoint CLI."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt

from waypoint import store
from waypoint.output import err
from waypoint.resolver import UsageError, validate_alias


class _Cancelled(Exception):
    """Interactive prompt aborted by the user (EOF / Ctrl+C / 'cancel')."""


def _resolve_collision(name: str, b: store.Bookmarks, console: Console) -> str | None:
    """Handle 'already exists' prompt. Returns new name, None to re-prompt, or raises _Cancelled."""
    try:
        choice = Prompt.ask(
            f"Bookmark {name!r} already exists -- override, rename, or cancel?",
            choices=["override", "rename", "cancel"],
        )
    except (EOFError, KeyboardInterrupt):
        raise _Cancelled from None
    if choice == "cancel":
        raise _Cancelled
    if choice == "rename":
        return None  # signal: re-prompt
    # "override": fall through with the same name
    return name


def prompt_name(b: store.Bookmarks, explicit: str | None, console: Console) -> str:
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
            err(console, f"{name!r} is not a valid bookmark name.")
            name = None
            continue
        if name in b.bookmarks:
            result = _resolve_collision(name, b, console)
            if result is None:
                name = None
                continue
            return result
        return name
