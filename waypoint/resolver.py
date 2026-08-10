"""Greedy alias parsing: reserved keywords first, anything else is a bookmark alias."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "RESERVED",
    "Command",
    "NavCmd",
    "AddCmd",
    "RmCmd",
    "LsCmd",
    "DefaultCmd",
    "SetCmd",
    "GetCmd",
    "ConfigCmd",
    "StoreCmd",
    "HelpCmd",
    "HistoryCmd",
    "UndoCmd",
    "OpenCmd",
    "RecordHistoryCmd",
    "UsageError",
    "parse_args",
    "validate_alias",
    "looks_like_path",
]

# `config` joins README's reserved list so that `wp config home <path>` (README,
# Data section) parses instead of being treated as a bookmark named "config".
RESERVED = {
    "_record_history",
    "add",
    "rm",
    "ls",
    "list",
    "default",
    "set",
    "get",
    "store",
    "config",
    "help",
    "undo",
    "u",
    "U",
    "uu",
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
class NavCmd:
    alias: str | None = None


@dataclass
class AddCmd:
    alias: str | None = None
    path: str | None = None


@dataclass
class RmCmd:
    alias: str


@dataclass
class LsCmd:
    pass


@dataclass
class DefaultCmd:
    arg: str


@dataclass
class SetCmd:
    arg: str | None = None


@dataclass
class GetCmd:
    alias: str | None = None


@dataclass
class ConfigCmd:
    target: str | None = None


@dataclass
class StoreCmd:
    arg: str | None = None


@dataclass
class HelpCmd:
    pass


@dataclass
class HistoryCmd:
    full: bool = False
    count: int | None = None


@dataclass
class UndoCmd:
    steps: int = 1


@dataclass
class OpenCmd:
    kind: str  # "explorer" or "code"


@dataclass
class RecordHistoryCmd:
    origin: str


Command = (
    NavCmd
    | AddCmd
    | RmCmd
    | LsCmd
    | DefaultCmd
    | SetCmd
    | GetCmd
    | ConfigCmd
    | StoreCmd
    | HelpCmd
    | HistoryCmd
    | UndoCmd
    | OpenCmd
    | RecordHistoryCmd
)


def parse_args(argv: list[str]) -> Command:
    """Parse the arguments after `wp`. First token: reserved keyword or bookmark alias."""
    if not argv:
        return NavCmd()
    head, rest = argv[0], argv[1:]
    if head not in RESERVED:
        return NavCmd(alias=head)
    if head == "_record_history":
        _require(rest, 1, "usage: wp _record_history <path>")
        return RecordHistoryCmd(origin=rest[0])
    if head in ("help", "-h", "-?"):
        _require(rest, 0, "wp help takes no arguments")
        return HelpCmd()
    if head in ("history", "h"):
        return _parse_history(rest)
    if head in ("undo", "u"):
        return _parse_undo(rest, default_steps=1)
    if head in ("U", "uu"):
        return _parse_undo(rest, default_steps=0)
    if head in (".", "-vs"):
        _require(rest, 0, f"wp {head} takes no arguments")
        return OpenCmd(kind="explorer" if head == "." else "code")
    if head in ("ls", "list"):
        _require(rest, 0, f"wp {head} takes no arguments")
        return LsCmd()
    if head == "add":
        return _parse_add(rest)
    if head == "rm":
        _require(rest, 1, "usage: wp rm <alias>")
        return RmCmd(alias=rest[0])
    if head == "default":
        _require(rest, 1, "usage: wp default <alias|path>")
        return DefaultCmd(arg=rest[0])
    if head == "set":
        if len(rest) > 1:
            raise UsageError("usage: wp set [alias|path]")
        if not rest:
            return SetCmd(arg=None)
        if rest[0] == ".":
            return SetCmd(arg=".")
        return SetCmd(arg=rest[0])
    if head == "get":
        if len(rest) > 1:
            raise UsageError("usage: wp get [alias]")
        return GetCmd(alias=rest[0] if rest else None)
    if head == "store":
        if not rest:
            return StoreCmd(arg=None)
        if len(rest) == 1:
            return StoreCmd(arg=rest[0])
        raise UsageError("usage: wp store [alias|path]")
    # config
    if not rest:
        return ConfigCmd(target=None)
    if rest == ["home"]:
        raise UsageError("usage: wp config home <path>")
    if len(rest) == 2 and rest[0] == "home":
        return ConfigCmd(target=rest[1])
    raise UsageError("usage: wp config [home <path>]")


FULL_FLAGS = ("--full", "--all", "full", "all", "f", "a")


def _parse_history(rest: list[str]) -> Command:
    """`wp history` default window; `--full` full stack; `N` rows (0 = current dir)."""
    if not rest:
        return HistoryCmd(full=False)
    if len(rest) == 1:
        if rest[0] in FULL_FLAGS:
            return HistoryCmd(full=True)
        if rest[0].isdigit() and int(rest[0]) >= 0:
            return HistoryCmd(count=int(rest[0]))
    raise UsageError("usage: wp history [--full|--all|full|all|f|a|[N]]")


def _parse_undo(rest: list[str], default_steps: int = 1) -> Command:
    """`wp undo` or `wp undo <N>`; N is a 0-based history row (0 = current dir, 1 = last jump)."""
    if len(rest) > 1:
        raise UsageError("usage: wp undo [N]")
    if not rest:
        return UndoCmd(steps=default_steps)
    n = rest[0]
    if not n.isdigit() or int(n) < 0:
        raise UsageError("usage: wp undo [N]  (N must be a non-negative integer)")
    return UndoCmd(steps=int(n))


def _parse_add(rest: list[str]) -> Command:
    if len(rest) > 2:
        raise UsageError("usage: wp add [alias] [path]")
    if len(rest) == 0:
        return AddCmd(alias=None, path=None)
    if len(rest) == 1:
        arg = rest[0]
        if arg == "." or looks_like_path(arg):
            # Path-form: bookmark this path, prompt for a name.
            return AddCmd(alias=None, path=arg)
        return AddCmd(alias=arg, path=None)
    # Two args: <alias> <path>. `wp add . dev` is shorthand for `wp add dev .`.
    alias, path = rest
    if alias == ".":
        alias, path = path, "."
    return AddCmd(alias=alias, path=path)


def looks_like_path(arg: str) -> bool:
    """Single-arg `wp add C:/x` or `wp add ~` means 'bookmark this path', not 'alias named C:/x'."""
    return arg == "~" or any(sep in arg for sep in ("\\", "/"))


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
