from __future__ import annotations

import io
import re
import types

from rich.console import Console

from waypoint import clipboard, store
from waypoint.commands.bookmarks import _add, _get, _ls, _mv, _rm, _row_style
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.resolver import AddCmd, GetCmd, MvCmd, RmCmd

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


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


# --- delete + recreate scenarios -------------------------------------------


def test_rm_default_then_recreate_restores_default(tmp_path, capsys):
    """Removing the default alias and re-adding it auto-restores the default."""
    console = Console()
    target = tmp_path / "proj"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(target)}, default="proj")
    store.save_bookmarks(b)

    cmd = RmCmd(alias="proj")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default is None

    cmd = AddCmd(alias="proj", path=str(target))
    rc = _add(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default == "proj"
    assert b.bookmarks["proj"] == str(target)


def test_rm_nondefault_then_recreate_does_not_set_default(tmp_path, capsys):
    """Removing a non-default alias and re-adding it does not touch the default."""
    console = Console()
    dev = tmp_path / "dev"
    web = tmp_path / "web"
    dev.mkdir()
    web.mkdir()
    b = store.Bookmarks(
        bookmarks={"dev": str(dev), "web": str(web)}, default="dev"
    )
    store.save_bookmarks(b)

    cmd = RmCmd(alias="web")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK

    cmd = AddCmd(alias="web", path=str(web))
    rc = _add(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default == "dev"
    assert "web" in b.bookmarks


def test_rm_default_then_explicit_default_clears_prev(tmp_path, capsys):
    """Explicitly setting a new default clears _prev_default."""
    console = Console()
    dev = tmp_path / "dev"
    web = tmp_path / "web"
    dev.mkdir()
    web.mkdir()
    b = store.Bookmarks(
        bookmarks={"dev": str(dev), "web": str(web)}, default="dev"
    )
    store.save_bookmarks(b)

    cmd = RmCmd(alias="dev")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b._prev_default == "dev"

    # Explicitly setting a new default clears _prev_default
    from waypoint.commands.bookmarks import _set_default
    rc = _set_default("web", console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default == "web"
    assert b._prev_default is None


def test_rm_then_recreate_different_alias_no_restore(tmp_path, capsys):
    """Re-adding under a different name does not restore the old default."""
    console = Console()
    target = tmp_path / "proj"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(target)}, default="proj")
    store.save_bookmarks(b)

    cmd = RmCmd(alias="proj")
    rc = _rm(cmd, console)
    assert rc == EXIT_OK

    cmd = AddCmd(alias="proj2", path=str(target))
    rc = _add(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default is None
    assert "proj2" in b.bookmarks


# --- wp mv tests -----------------------------------------------------------


def test_mv_repoints_bookmark(tmp_path, capsys):
    console = Console()
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(old)}, default=None)
    store.save_bookmarks(b)

    cmd = MvCmd(alias="proj", new_path=str(new))
    rc = _mv(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.bookmarks["proj"] == str(new)


def test_mv_preserves_default(tmp_path, capsys):
    console = Console()
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(old)}, default="proj")
    store.save_bookmarks(b)

    cmd = MvCmd(alias="proj", new_path=str(new))
    rc = _mv(cmd, console)
    assert rc == EXIT_OK
    b = store.load_bookmarks()
    assert b.default == "proj"
    assert b.bookmarks["proj"] == str(new)


def test_mv_nonexistent_alias_errors(tmp_path, capsys):
    console = Console()
    target = tmp_path / "somewhere"
    target.mkdir()

    cmd = MvCmd(alias="nope", new_path=str(target))
    rc = _mv(cmd, console)
    assert rc == EXIT_ERROR


def test_mv_nonexistent_path_errors(tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={"proj": str(tmp_path)}, default=None)
    store.save_bookmarks(b)

    cmd = MvCmd(alias="proj", new_path=str(tmp_path / "nope"))
    rc = _mv(cmd, console)
    assert rc == EXIT_ERROR


def test_row_style_dead_is_dimmed():
    assert _row_style(has_default=True, is_cwd=True, is_alive=False) == "dim"
    assert _row_style(has_default=False, is_cwd=False, is_alive=False) == "dim"
    assert _row_style(has_default=True, is_cwd=False, is_alive=True) == "bold green"


def test_ls_flags_missing_path(tmp_path, capsys):
    console = Console()
    gone = tmp_path / "gone"
    alive = tmp_path / "alive"
    alive.mkdir()
    b = store.Bookmarks(
        bookmarks={"dead": str(gone), "live": str(alive)}, default=None
    )
    store.save_bookmarks(b)

    rc = _ls(console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "MISSING" in out
    assert "1 bookmark(s) point to missing paths" in out


def test_ls_missing_warning_renders_command_without_literal_tags(tmp_path):
    """The "wp mv" advice in the missing-paths warning is [bold]-tagged. warn()
    used to escape it, so the user saw a literal "[bold]wp mv ...[/bold]"."""
    gone = tmp_path / "gone"
    b = store.Bookmarks(bookmarks={"dead": str(gone)}, default=None)
    store.save_bookmarks(b)

    buf = io.StringIO()
    console = Console(
        file=buf,
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
        highlight=False,
        width=200,
    )
    assert _ls(console) == EXIT_OK

    plain = _ANSI.sub("", buf.getvalue())
    assert "[bold]" not in plain
    assert "[/bold]" not in plain
    assert "use wp mv <alias> <new_path> to repoint" in plain


def test_ls_all_alive_no_warning(tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={"dev": str(tmp_path)}, default=None)
    store.save_bookmarks(b)

    rc = _ls(console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "MISSING" not in out
    assert "point to missing" not in out


def test_ls_missing_marker_is_not_dimmed(tmp_path):
    """The dead-row base style is "dim" and inline tags only override the
    properties they name, so a bare [red] marker inherits dim and renders
    fainter than the live path beside it. Lock the plain-red emission."""
    gone = tmp_path / "gone"
    b = store.Bookmarks(bookmarks={"dead": str(gone)}, default=None)
    store.save_bookmarks(b)

    buf = io.StringIO()
    console = Console(
        file=buf,
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
        highlight=False,
        width=120,
    )
    assert _ls(console) == EXIT_OK

    out = buf.getvalue()
    assert "\x1b[31m[MISSING]" in out
    assert "\x1b[2;31m[MISSING]" not in out


def test_ls_escapes_bracketed_path_segment(tmp_path):
    """A path segment in [brackets] must survive rich's tag regex intact."""
    target = tmp_path / "[draft]"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"proj": str(target)}, default=None)
    store.save_bookmarks(b)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, highlight=False, width=120)
    assert _ls(console) == EXIT_OK

    assert str(target) in buf.getvalue()
