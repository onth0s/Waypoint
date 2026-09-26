"""Formatted output helpers for the Waypoint CLI.

Centralizes all rich markup so cli.py never embeds format strings.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

__all__ = ["err", "ok", "warn", "hint"]


def err(console: Console, msg: str | Exception) -> None:
    """Print a red error line. soft_wrap keeps an embedded path on one line.

    Escapes markup: pass paths, aliases, and exception text here. To attach
    advice to an error, print it separately with hint() rather than inlining
    tags -- err() would escape them into visible [bold] garbage.
    """
    console.print(f"[bold red]Error:[/bold red] {escape(str(msg))}", soft_wrap=True)


def ok(console: Console, msg: str) -> None:
    """Print a green success line. soft_wrap keeps an embedded path on one line.

    Escapes markup, same contract as err().
    """
    console.print(f"[bold green]{escape(msg)}[/bold green]", soft_wrap=True)


def warn(console: Console, msg: str) -> None:
    """Print a yellow warning line. Keeps inline markup (pairs with hint()).

    Callers pass static advice text, often with [bold] tags for the command to
    run. escape() is deliberately NOT applied: doing so renders the tags
    literally. Any dynamic value interpolated into msg must be escape()d by the
    caller.
    """
    console.print(f"[yellow]Warning:[/yellow] {msg}")


def hint(console: Console, msg: str) -> None:
    """Print an informational hint line (cyan, keeps inline markup).

    Caller must escape() any dynamic value interpolated into msg.
    """
    console.print(f"[cyan]{msg}[/cyan]")

