"""Output helper tests."""

from io import StringIO

from rich.console import Console

from waypoint.output import err, hint, ok, warn


def _make_console():
    return Console(file=StringIO(), force_terminal=True)


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
