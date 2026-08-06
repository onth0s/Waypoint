from __future__ import annotations

import types

from rich.console import Console

from waypoint import clipboard, store
from waypoint.commands.bookmarks import _add, _get, _ls, _rm, _row_style
from waypoint.constants import EXIT_OK
from waypoint.resolver import AddCmd, GetCmd, RmCmd


def test_add_explicit_alias_and_path(tmp_path, capsys):
    console = Console()
    target = tmp_path / "work"
    target.mkdir()

    cmd = AddCmd(alias="work", path=str(target))
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

    cmd = RmCmd(alias="work")
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


def test_rm_star_alias_vs_suffix(tmp_path):
    console = Console()
    target_dev = tmp_path / "dev"
    target_star = tmp_path / "devstar"
    target_dev.mkdir()
    target_star.mkdir()

    b = store.Bookmarks(
        bookmarks={"dev": str(target_dev), "dev*": str(target_star)}, default="dev"
    )
    store.save_bookmarks(b)

    # wp rm dev* removes dev*, leaving dev
    cmd = RmCmd(alias="dev*")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert "dev*" not in b.bookmarks
    assert "dev" in b.bookmarks
    assert b.default == "dev"

    # wp rm "dev *" removes default dev (using ls label syntax)
    cmd = RmCmd(alias="dev *")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert "dev" not in b.bookmarks
    assert b.default is None


def test_ls_empty_bookmarks(capsys):
    console = Console()
    store.save_bookmarks(store.Bookmarks(bookmarks={}, default=None))
    rc = _ls(console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "No bookmarks yet" in out


def test_get_copies_and_prints(tmp_path, capsys, monkeypatch):
    console = Console()
    target = tmp_path / "prof"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"prof": str(target)}, default=None)
    store.save_bookmarks(b)

    copied = []
    monkeypatch.setattr(clipboard, "pyperclip", types.SimpleNamespace(copy=copied.append))

    rc = _get(GetCmd(alias="prof"), console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert copied == [str(target)]
    assert str(target) in out


def test_get_default_when_no_alias(tmp_path, capsys, monkeypatch):
    console = Console()
    target = tmp_path / "dev"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"dev": str(target)}, default="dev")
    store.save_bookmarks(b)

    copied = []
    monkeypatch.setattr(clipboard, "pyperclip", types.SimpleNamespace(copy=copied.append))

    rc = _get(GetCmd(alias=None), console)
    capsys.readouterr()
    assert rc == EXIT_OK
    assert copied == [str(target)]


def test_row_style_combinations():
    assert _row_style(has_default=False, is_cwd=False) is None
    assert _row_style(has_default=True, is_cwd=False) == "bold green"
    assert _row_style(has_default=False, is_cwd=True) == "bold white on bright_black"
    assert _row_style(has_default=True, is_cwd=True) == "bold green on bright_black"


def test_ls_highlights_current_dir(monkeypatch, tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={"here": str(tmp_path)}, default=None)
    store.save_bookmarks(b)
    monkeypatch.chdir(tmp_path)

    rc = _ls(console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "here" in out
