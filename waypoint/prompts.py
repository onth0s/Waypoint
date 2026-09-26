"""Interactive prompts for the Waypoint CLI."""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, DefaultType, Prompt
from rich.text import Text

from waypoint import store
from waypoint.output import err, hint
from waypoint.resolver import UsageError, validate_alias


class _Cancelled(Exception):
    """Interactive prompt aborted by the user (EOF / Ctrl+C / 'cancel')."""


class _YesNo(Confirm):
    """Confirm that renders the conventional ``[y/N]``.

    rich's stock Confirm joins ``self.choices`` verbatim, giving a flat ``[y/n]``
    and then repeating the default as ``(n)``. ``choices`` stays lowercase here
    so the inherited process_response keeps matching input case-insensitively.
    """

    def make_prompt(self, default: DefaultType) -> Text:
        yes, no = self.choices
        if default is False:
            yes, no = "y", "N"
        elif default is True:
            yes, no = "Y", "n"
        prompt = self.prompt.copy()
        prompt.end = ""
        prompt.append(f" [{yes}/{no}]", "prompt.choices")
        prompt.append(self.prompt_suffix)
        return prompt


def confirm_create(target: str) -> bool:
    """Ask to create a missing directory. False on decline; raises _Cancelled on abort."""
    try:
        return _YesNo.ask(f"Create [bold]{escape(target)}[/bold]?", default=False)
    except (EOFError, KeyboardInterrupt):
        raise _Cancelled from None


def _resolve_collision(name: str, b: store.Bookmarks, console: Console) -> str | None:
    """Handle 'already exists' prompt. Returns new name, None to re-prompt, or raises _Cancelled."""
    try:
        choice = Prompt.ask(
            f"Bookmark {name!r} already exists -- (o)verride, (r)ename, or (c)ancel?",
            choices=["o", "r", "c", "override", "rename", "cancel"],
        )
    except (EOFError, KeyboardInterrupt):
        raise _Cancelled from None
    if choice in ("c", "cancel"):
        raise _Cancelled
    if choice in ("r", "rename"):
        return None  # signal: re-prompt
    # "o" / "override": fall through with the same name
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
            hint(
                console,
                f"Hint: [bold]wp mv {escape(name)} <new_path>[/bold] to repoint instead.",
            )
            result = _resolve_collision(name, b, console)
            if result is None:
                name = None
                continue
            return result
        return name
