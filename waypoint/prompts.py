"""Interactive prompts for the Waypoint CLI."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

from waypoint import store
from waypoint.constants import EXIT_ERROR, WaypointError
from waypoint.output import err, hint
from waypoint.resolver import UsageError, validate_alias


class PromptCancelled(WaypointError):
    """Interactive prompt aborted by the user (EOF / Ctrl+C / 'cancel')."""
    exit_code: int = EXIT_ERROR


# Backward-compatibility alias
_Cancelled = PromptCancelled


def resolve_collision(name: str, b: store.Bookmarks, console: Console) -> str | None:
    """Handle 'already exists' prompt.

    Returns new name, None to re-prompt, or raises PromptCancelled.
    """
    try:
        choice = Prompt.ask(
            f"Bookmark {name!r} already exists -- (o)verride, (r)ename, or (c)ancel?",
            choices=["o", "r", "c", "override", "rename", "cancel"],
        )
    except (EOFError, KeyboardInterrupt):
        raise PromptCancelled from None
    if choice in ("c", "cancel"):
        raise PromptCancelled
    if choice in ("r", "rename"):
        return None  # signal: re-prompt
    # "o" / "override": fall through with the same name
    return name


# Backward-compatibility alias
_resolve_collision = resolve_collision


def prompt_name(b: store.Bookmarks, explicit: str | None, console: Console) -> str:
    """Return a valid, non-colliding bookmark name; prompt when the alias is absent."""
    name = explicit
    while True:
        if name is None:
            try:
                name = Prompt.ask("[bold]Bookmark name[/bold]")
            except (EOFError, KeyboardInterrupt):
                raise PromptCancelled from None
        try:
            validate_alias(name)
        except UsageError:
            if explicit is not None:
                raise  # bad explicit alias -> usage error, exit 2
            err(console, f"{name!r} is not a valid bookmark name.")
            name = None
            continue
        if name in b.bookmarks:
            hint(
                console,
                f"Hint: [bold]wp mv {escape(name)} <new_path>[/bold] to repoint instead.",
            )
            result = resolve_collision(name, b, console)
            if result is None:
                name = None
                continue
            return result
        return name
