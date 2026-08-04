"""Formatted output helpers for the Waypoint CLI.

Centralizes all rich markup so cli.py never embeds format strings.
"""

from __future__ import annotations

from rich.console import Console

__all__ = ["err", "ok", "warn", "hint"]


def err(console: Console, msg: str | Exception) -> None:
    """Print a red error line."""
    console.print(f"[bold red]Error:[/bold red] {msg}")


def ok(console: Console, msg: str) -> None:
    """Print a green success line."""
    console.print(f"[bold green]{msg}[/bold green]")


def warn(console: Console, msg: str) -> None:
    """Print a yellow warning line."""
    console.print(f"[yellow]Warning:[/yellow] {msg}")


def hint(console: Console, msg: str) -> None:
    """Print an informational hint."""
    console.print(msg)
