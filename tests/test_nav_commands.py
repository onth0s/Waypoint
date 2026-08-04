from __future__ import annotations

from rich.console import Console

from waypoint import store
from waypoint.commands import _nav
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.resolver import Command


def test_nav_default_bookmark(tmp_path, capsys):
    console = Console()
    target = tmp_path / "target"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"myalias": str(target)}, default="myalias")
    store.save_bookmarks(b)

    cmd = Command(kind="nav", args=[])
    rc = _nav(cmd, console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert out.strip() == str(target)


def test_nav_alias_bookmark(tmp_path, capsys):
    console = Console()
    target = tmp_path / "target"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(target)}, default=None)
    store.save_bookmarks(b)

    cmd = Command(kind="nav", args=["proj"])
    rc = _nav(cmd, console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert out.strip() == str(target)


def test_nav_missing_alias(tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={}, default=None)
    store.save_bookmarks(b)

    cmd = Command(kind="nav", args=["nonexistent"])
    rc = _nav(cmd, console)
    assert rc == EXIT_ERROR


def test_record_origin_case_insensitive(tmp_path, monkeypatch):
    from waypoint.commands.nav import _record_origin
    monkeypatch.chdir(tmp_path)

    # Path with different casing on Windows (e.g., upper/lower case drive/dir)
    different_case = str(tmp_path).upper() if str(tmp_path).islower() else str(tmp_path).lower()
    _record_origin(different_case)

    # History should remain empty because normcase recognizes origin == target
    assert store.load_history() == []

