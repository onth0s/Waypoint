"""Greedy alias parsing: reserved keywords first, anything else is a bookmark alias."""

from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["RESERVED", "Command", "UsageError", "parse_args", "validate_alias", "looks_like_path"]

# `config` joins README's reserved list so that `wp config home <path>` (README,
# Data section) parses instead of being treated as a bookmark named "config".
RESERVED = {
    "add",
    "rm",
    "ls",
    "list",
    "default",
    "set",
    "config",
    "help",
    "undo",
    "u",
    "history",
    "h",
    ".",
    "-vs",
    "-h",
    "-?",
}


class UsageError(Exception):
    """Raised on malformed invocations; the cli turns it into an exit code 2."""


@dataclass
class Command:
    kind: str  # nav | add | rm | ls | default | set | config | help | explorer | code
    args: list[str | None]  # shape is per-kind, see parse_args


def parse_args(argv: list[str]) -> Command:
    """Parse the arguments after `wp`. First token: reserved keyword or bookmark alias."""
    if not argv:
        return Command(kind="nav", args=[])
    head, rest = argv[0], argv[1:]
    if head not in RESERVED:
        return Command(kind="nav", args=[head])
    if head in ("help", "-h", "-?"):
        _require(rest, 0, "wp help takes no arguments")
        return Command(kind="help", args=[])
    if head in ("history", "h"):
        return _parse_history(rest)
    if head in ("undo", "u"):
        return _parse_undo(rest)
    if head in (".", "-vs"):
        _require(rest, 0, f"wp {head} takes no arguments")
        return Command(kind="explorer" if head == "." else "code", args=[])
    if head in ("ls", "list"):
        _require(rest, 0, f"wp {head} takes no arguments")
        return Command(kind="ls", args=[])
    if head == "add":
        return _parse_add(rest)
    if head == "rm":
        _require(rest, 1, "usage: wp rm <alias>")
        return Command(kind="rm", args=[rest[0]])
    if head == "default":
        _require(rest, 1, "usage: wp default <alias|path>")
        return Command(kind="default", args=[rest[0]])
    if head == "set":
        if len(rest) > 1:
            raise UsageError("usage: wp set [alias|path]")
        if not rest:
            return Command(kind="set", args=[None])
        if rest[0] == ".":
            return Command(kind="set", args=["."])
        return Command(kind="set", args=[rest[0]])
    # config
    if not rest:
        return Command(kind="config", args=[None])
    if rest == ["home"]:
        raise UsageError("usage: wp config home <path>")
    if len(rest) == 2 and rest[0] == "home":
        return Command(kind="config", args=["home", rest[1]])
    raise UsageError("usage: wp config [home <path>]")


FULL_FLAGS = ("--full", "--all", "full", "all", "f", "a")


def _parse_history(rest: list[str]) -> Command:
    """`wp history` shows the default window; a full flag shows the whole stack."""
    if not rest:
        return Command(kind="history", args=[None])
    if len(rest) == 1 and rest[0] in FULL_FLAGS:
        return Command(kind="history", args=["all"])
    raise UsageError("usage: wp history [--full|--all|full|all|f|a]")


def _parse_undo(rest: list[str]) -> Command:
    """`wp undo` or `wp undo <N>`; N must be a positive integer (steps back)."""
    if len(rest) > 1:
        raise UsageError("usage: wp undo [N]")
    if not rest:
        return Command(kind="undo", args=[None])
    n = rest[0]
    if not n.isdigit() or int(n) < 1:
        raise UsageError("usage: wp undo [N]  (N must be a positive integer)")
    return Command(kind="undo", args=[n])


def _parse_add(rest: list[str]) -> Command:
    if len(rest) > 2:
        raise UsageError("usage: wp add [alias] [path]")
    if len(rest) == 0:
        return Command(kind="add", args=[None, None])
    if len(rest) == 1:
        arg = rest[0]
        if arg == "." or looks_like_path(arg):
            # Path-form: bookmark this path, prompt for a name.
            return Command(kind="add", args=[None, arg])
        return Command(kind="add", args=[arg, None])
    # Two args: <alias> <path>. `wp add . dev` is shorthand for `wp add dev .`.
    alias, path = rest
    if alias == ".":
        alias, path = path, "."
    return Command(kind="add", args=[alias, path])


def looks_like_path(arg: str) -> bool:
    """Single-arg `wp add C:/x` means "bookmark this path", not "alias named C:/x"."""
    return any(sep in arg for sep in ("\\", "/")) or os.path.isdir(arg)


def _require(rest: list[str], count: int, message: str) -> None:
    if len(rest) != count:
        raise UsageError(message)


def validate_alias(name: str) -> None:
    """Reject names that would break lookup: empty, whitespace, reserved words."""
    if not name:
        raise UsageError("bookmark name can't be empty")
    if any(ch.isspace() for ch in name):
        raise UsageError(f"bookmark name can't contain spaces: {name!r}")
    if name in RESERVED:
        raise UsageError(f"{name!r} is a reserved word and can't be a bookmark name")
