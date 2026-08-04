from __future__ import annotations

from rich.console import Console

from waypoint import store
from waypoint.commands import _add, _ls, _rm
from waypoint.constants import EXIT_OK
from waypoint.resolver import Command


def test_add_explicit_alias_and_path(tmp_path, capsys):
    console = Console()
    target = tmp_path / "work"
    target.mkdir()

    cmd = Command(kind="add", args=["work", str(target)])
    rc = _add(cmd, console)
    assert rc == EXIT_OK

    b = store.load_bookmarks()
    assert b.bookmarks["work"] == str(target)


def test_rm_bookmark(tmp_path, capsys):
    console = Console()
    target = tmp_path / "work"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"work": str(target)}, default="work")
    store.save_bookmarks(b)

    cmd = Command(kind="rm", args=["work"])
    rc = _rm(cmd, console)
    assert rc == EXIT_OK

    b = store.load_bookmarks()
    assert "work" not in b.bookmarks
    assert b.default is None


def test_ls_bookmarks(tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={"dev": str(tmp_path)}, default="dev")
    store.save_bookmarks(b)

    rc = _ls(console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "dev *" in out
