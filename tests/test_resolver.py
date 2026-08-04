"""Resolver tests: greedy alias parsing, add-form disambiguation, alias validation."""

import pytest

from waypoint.resolver import RESERVED, Command, UsageError, parse_args, validate_alias


@pytest.mark.parametrize(
    ("argv", "kind", "args"),
    [
        ([], "nav", []),
        (["dev"], "nav", ["dev"]),
        (["add"], "add", [None, None]),
        (["add", "dev"], "add", ["dev", None]),
        (["add", "."], "add", [None, "."]),
        (["add", "dev", "."], "add", ["dev", "."]),
        (["add", ".", "dev"], "add", ["dev", "."]),  # shorthand for `add dev .`
        (["add", r"C:\path"], "add", [None, r"C:\path"]),
        (["add", "dev", r"C:\path"], "add", ["dev", r"C:\path"]),
        (["rm", "dev"], "rm", ["dev"]),
        (["ls"], "ls", []),
        (["list"], "ls", []),
        (["default", "dev"], "default", ["dev"]),
        (["default", "."], "default", ["."]),
        (["default", r"C:\path"], "default", [r"C:\path"]),
        (["set"], "set", [None]),
        (["set", "."], "set", ["."]),
        (["set", "dev"], "set", ["dev"]),
        (["set", r"C:\path"], "set", [r"C:\path"]),
        (["config"], "config", [None]),
        (["config", "home", r"C:\home"], "config", ["home", r"C:\home"]),
        (["help"], "help", []),
        (["-h"], "help", []),
        (["-?"], "help", []),
        (["history"], "history", [None]),
        (["h"], "history", [None]),
        (["history", "--all"], "history", ["all"]),
        (["history", "--full"], "history", ["all"]),
        (["history", "all"], "history", ["all"]),
        (["history", "full"], "history", ["all"]),
        (["history", "a"], "history", ["all"]),
        (["history", "f"], "history", ["all"]),
        (["h", "--all"], "history", ["all"]),
        (["h", "a"], "history", ["all"]),
        (["undo"], "undo", [None]),
        (["u"], "undo", [None]),
        (["undo", "3"], "undo", ["3"]),
        (["u", "2"], "undo", ["2"]),
        (["."], "explorer", []),
        (["-vs"], "code", []),
    ],
)
def test_parse_args(argv, kind, args):
    cmd = parse_args(argv)
    assert cmd == Command(kind=kind, args=args)


def test_add_existing_dir_is_path_form(tmp_path):
    cmd = parse_args(["add", str(tmp_path)])
    assert cmd == Command(kind="add", args=[None, str(tmp_path)])


@pytest.mark.parametrize(
    "argv",
    [
        ["rm"],
        ["rm", "a", "b"],
        ["default"],
        ["default", "a", "b"],
        ["set", "a", "b"],
        ["ls", "x"],
        ["list", "x"],
        ["help", "x"],
        ["history", "x"],
        ["history", "--full", "extra"],
        ["h", "x"],
        ["h", "a", "b"],
        ["undo", "x"],
        ["undo", "0"],
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
        assert cmd.kind != "nav"
