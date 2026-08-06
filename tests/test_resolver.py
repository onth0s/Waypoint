"""Resolver tests: greedy alias parsing, add-form disambiguation, alias validation."""

import pytest

from waypoint.resolver import (
    RESERVED,
    AddCmd,
    ConfigCmd,
    DefaultCmd,
    GetCmd,
    HelpCmd,
    HistoryCmd,
    LsCmd,
    NavCmd,
    OpenCmd,
    RecordHistoryCmd,
    RmCmd,
    SetCmd,
    StoreCmd,
    UndoCmd,
    UsageError,
    parse_args,
    validate_alias,
)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        ([], NavCmd()),
        (["dev"], NavCmd(alias="dev")),
        (["_record_history", r"C:\path"], RecordHistoryCmd(origin=r"C:\path")),
        (["add"], AddCmd(alias=None, path=None)),
        (["add", "dev"], AddCmd(alias="dev", path=None)),
        (["add", "."], AddCmd(alias=None, path=".")),
        (["add", "dev", "."], AddCmd(alias="dev", path=".")),
        (["add", ".", "dev"], AddCmd(alias="dev", path=".")),  # shorthand for `add dev .`
        (["add", r"C:\path"], AddCmd(alias=None, path=r"C:\path")),
        (["add", "dev", r"C:\path"], AddCmd(alias="dev", path=r"C:\path")),
        (["rm", "dev"], RmCmd(alias="dev")),
        (["ls"], LsCmd()),
        (["list"], LsCmd()),
        (["default", "dev"], DefaultCmd(arg="dev")),
        (["default", "."], DefaultCmd(arg=".")),
        (["default", r"C:\path"], DefaultCmd(arg=r"C:\path")),
        (["set"], SetCmd(arg=None)),
        (["set", "."], SetCmd(arg=".")),
        (["set", "dev"], SetCmd(arg="dev")),
        (["set", r"C:\path"], SetCmd(arg=r"C:\path")),
        (["get"], GetCmd(alias=None)),
        (["get", "dev"], GetCmd(alias="dev")),
        (["config"], ConfigCmd(target=None)),
        (["config", "home", r"C:\home"], ConfigCmd(target=r"C:\home")),
        (["store"], StoreCmd(arg=None)),
        (["store", "dev"], StoreCmd(arg="dev")),
        (["store", r"C:\home"], StoreCmd(arg=r"C:\home")),
        (["help"], HelpCmd()),
        (["-h"], HelpCmd()),
        (["-?"], HelpCmd()),
        (["history"], HistoryCmd(full=False)),
        (["h"], HistoryCmd(full=False)),
        (["history", "3"], HistoryCmd(count=3)),
        (["h", "2"], HistoryCmd(count=2)),
        (["history", "0"], HistoryCmd(count=0)),
        (["h", "0"], HistoryCmd(count=0)),
        (["history", "--all"], HistoryCmd(full=True)),
        (["history", "--full"], HistoryCmd(full=True)),
        (["history", "all"], HistoryCmd(full=True)),
        (["history", "full"], HistoryCmd(full=True)),
        (["history", "a"], HistoryCmd(full=True)),
        (["history", "f"], HistoryCmd(full=True)),
        (["h", "--all"], HistoryCmd(full=True)),
        (["h", "a"], HistoryCmd(full=True)),
        (["undo"], UndoCmd(steps=1)),
        (["u"], UndoCmd(steps=1)),
        (["undo", "3"], UndoCmd(steps=3)),
        (["u", "2"], UndoCmd(steps=2)),
        (["undo", "0"], UndoCmd(steps=0)),
        (["u", "0"], UndoCmd(steps=0)),
        (["."], OpenCmd(kind="explorer")),
        (["-vs"], OpenCmd(kind="code")),
    ],
)
def test_parse_args(argv, expected):
    cmd = parse_args(argv)
    assert cmd == expected


def test_add_existing_dir_is_path_form(tmp_path):
    cmd = parse_args(["add", str(tmp_path)])
    assert cmd == AddCmd(alias=None, path=str(tmp_path))


@pytest.mark.parametrize(
    "argv",
    [
        ["rm"],
        ["rm", "a", "b"],
        ["default"],
        ["default", "a", "b"],
        ["set", "a", "b"],
        ["get", "a", "b"],
        ["ls", "x"],
        ["list", "x"],
        ["help", "x"],
        ["history", "x"],
        ["history", "--full", "extra"],
        ["h", "x"],
        ["h", "a", "b"],
        ["undo", "x"],
        ["undo", "-1"],
        ["undo", "1", "2"],
        ["u", "1", "2"],
        [".", "x"],
        ["-vs", "x"],
        ["add", "a", "b", "c"],
        ["config", "foo"],
        ["config", "home"],
        ["config", "home", "a", "b"],
    ],
)
def test_usage_errors(argv):
    with pytest.raises(UsageError):
        parse_args(argv)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "my alias",
        "add",
        "rm",
        "ls",
        "list",
        "default",
        "set",
        "get",
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
    ],
)
def test_validate_alias_rejects(name):
    with pytest.raises(UsageError):
        validate_alias(name)


def test_validate_alias_accepts_plain_name():
    validate_alias("dev")  # no exception


def test_reserved_set_matches_parser():
    # Every reserved keyword must dispatch to a subcommand or a usage error,
    # never to nav (greedy alias rule must not swallow reserved words).
    for keyword in RESERVED:
        try:
            cmd = parse_args([keyword])
        except UsageError:
            continue  # arg-requiring keywords (rm, default) with no args
        assert not isinstance(cmd, NavCmd)
