"""Formatted output helpers for the Waypoint CLI.

Centralizes all rich markup so cli.py never embeds format strings.
"""

from __future__ import annotations

from rich.console import Console
from rich.markup import escape

__all__ = ["err", "ok", "warn", "hint"]


def err(console: Console, msg: str | Exception) -> None:
    """Print a red error line. soft_wrap keeps an embedded path on one line."""
    console.print(f"[bold red]Error:[/bold red] {escape(str(msg))}", soft_wrap=True)


def ok(console: Console, msg: str) -> None:
    """Print a green success line. soft_wrap keeps an embedded path on one line."""
    console.print(f"[bold green]{escape(msg)}[/bold green]", soft_wrap=True)


def warn(console: Console, msg: str) -> None:
    """Print a yellow warning line."""
    console.print(f"[yellow]Warning:[/yellow] {escape(msg)}")


def hint(console: Console, msg: str) -> None:
    """Print an informational hint."""
    console.print(msg)
