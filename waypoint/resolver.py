"""Greedy alias parsing: reserved keywords first, anything else is a bookmark alias."""

from __future__ import annotations

import os
from dataclasses import dataclass

# `config` joins README's reserved list so that `wp config home <path>` (README,
# Data section) parses instead of being treated as a bookmark named "config".
RESERVED = {"add", "rm", "ls", "default", "config", "help", ".", "-vs", "-h", "-?"}


class UsageError(Exception):
    """Raised on malformed invocations; the cli turns it into an exit code 2."""


@dataclass
class Command:
    kind: str  # nav | add | rm | ls | default | config | help | explorer | code
    args: list  # list[str | None]; shape is per-kind, see parse_args


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
    if head in (".", "-vs"):
        _require(rest, 0, f"wp {head} takes no arguments")
        return Command(kind="explorer" if head == "." else "code", args=[])
    if head == "ls":
        _require(rest, 0, "wp ls takes no arguments")
        return Command(kind="ls", args=[])
    if head == "add":
        return _parse_add(rest)
    if head == "rm":
        _require(rest, 1, "usage: wp rm <alias>")
        return Command(kind="rm", args=[rest[0]])
    if head == "default":
        _require(rest, 1, "usage: wp default <alias|path>")
        return Command(kind="default", args=[rest[0]])
    # config
    if not rest:
        return Command(kind="config", args=[None])
    if rest == ["home"]:
        raise UsageError("usage: wp config home <path>")
    if len(rest) == 2 and rest[0] == "home":
        return Command(kind="config", args=["home", rest[1]])
    raise UsageError("usage: wp config [home <path>]")


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
