"""Output helper tests."""

import re
from io import StringIO

from rich.console import Console

from waypoint.output import err, hint, ok, warn

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _make_console():
    return Console(file=StringIO(), force_terminal=True)


def _make_color_console():
    """Production-shaped console: forced color, no ReprHighlighter noise."""
    return Console(
        file=StringIO(),
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
        highlight=False,
        width=200,
    )


def test_err_prints_red():
    console = _make_console()
    err(console, "test message")
    out = console.file.getvalue()
    assert "Error" in out
    assert "test message" in out


def test_ok_prints_green():
    console = _make_console()
    ok(console, "saved")
    out = console.file.getvalue()
    assert "saved" in out


def test_warn_prints_yellow():
    console = _make_console()
    warn(console, "careful")
    out = console.file.getvalue()
    assert "Warning" in out
    assert "careful" in out


def test_hint_prints_plain():
    console = _make_console()
    hint(console, "try wp help")
    out = console.file.getvalue()
    assert "try wp help" in out


def test_warn_renders_inline_markup_instead_of_literal_tags():
    """warn() carries static advice text with [bold] tags. escape() used to be
    applied here, which rendered the tags as visible "[bold]wp mv ...[/bold]"."""
    console = _make_color_console()
    warn(console, "use [bold]wp mv <alias> <new_path>[/bold] to repoint")
    raw = console.file.getvalue()
    plain = _ANSI.sub("", raw)
    assert "[bold]" not in plain
    assert "[/bold]" not in plain
    assert "use wp mv <alias> <new_path> to repoint" in plain
    assert "1" in raw  # bold SGR somewhere in the command span


def test_hint_renders_inline_markup_instead_of_literal_tags():
    console = _make_color_console()
    hint(console, "run [bold]wp h --all[/bold]")
    plain = _ANSI.sub("", console.file.getvalue())
    assert "[bold]" not in plain
    assert "run wp h --all" in plain


def test_err_keeps_escaping_markup_in_data():
    """err() is the data-carrying half of the contract: paths and aliases must
    survive verbatim and must never be interpreted as markup."""
    console = _make_color_console()
    err(console, "not a directory: C:\\dev\\[draft]\\proj")
    plain = _ANSI.sub("", console.file.getvalue())
    assert "C:\\dev\\[draft]\\proj" in plain


def test_ok_keeps_escaping_markup_in_data():
    console = _make_color_console()
    ok(console, "Saved demo -> C:\\dev\\[draft]")
    plain = _ANSI.sub("", console.file.getvalue())
    assert "C:\\dev\\[draft]" in plain


def test_ok_long_path_stays_single_line():
    """A long path in a confirmation must not fold mid-word under a narrow pipe."""
    console = Console(file=StringIO(), width=20, force_terminal=False)
    long_path = "C:/a/very/long/directory/path/that/exceeds/the/narrow/width"
    ok(console, f"Saved demo -> {long_path}")
    out = console.file.getvalue()
    lines = out.splitlines()
    assert len(lines) == 1
    assert f"Saved demo -> {long_path}" in lines[0]


def test_err_long_path_stays_single_line():
    console = Console(file=StringIO(), width=20, force_terminal=False)
    long_path = "C:/a/very/long/directory/path/that/exceeds/the/narrow/width"
    err(console, f"not a directory: {long_path}")
    out = console.file.getvalue()
    lines = out.splitlines()
    assert len(lines) == 1
    assert f"not a directory: {long_path}" in lines[0]
