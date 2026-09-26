from __future__ import annotations

import io
import re

from rich.console import Console

from waypoint import store
from waypoint.commands.nav import NAV_OUT_ENV, _nav, _record_origin
from waypoint.constants import EXIT_ERROR, EXIT_OK
from waypoint.resolver import NavCmd

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _color_console():
    """Production-shaped console: forced color, no ReprHighlighter noise."""
    return Console(
        file=io.StringIO(),
        force_terminal=True,
        color_system="standard",
        legacy_windows=False,
        highlight=False,
        width=200,
    )


def test_nav_default_bookmark(tmp_path, capsys):
    console = Console()
    target = tmp_path / "target"
    target.mkdir()
    b = store.Bookmarks(bookmarks={"myalias": str(target)}, default="myalias")
    store.save_bookmarks(b)

    cmd = NavCmd(alias=None)
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

    cmd = NavCmd(alias="proj")
    rc = _nav(cmd, console)
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert out.strip() == str(target)


def test_nav_missing_alias(tmp_path, capsys):
    console = Console()
    b = store.Bookmarks(bookmarks={}, default=None)
    store.save_bookmarks(b)

    cmd = NavCmd(alias="nonexistent")
    rc = _nav(cmd, console)
    assert rc == EXIT_ERROR


def test_record_origin_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Path with different casing on Windows (e.g., upper/lower case drive/dir)
    different_case = str(tmp_path).upper() if str(tmp_path).islower() else str(tmp_path).lower()
    _record_origin(different_case)

    # History should remain empty because normcase recognizes origin == target
    assert store.load_history() == []


def test_nav_missing_dir_points_at_force_flag(tmp_path):
    """A missing target must advertise the -F recovery, without creating anything."""
    console = _color_console()
    gone = tmp_path / "gone"
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(gone)}, default=None))

    rc = _nav(NavCmd(alias="proj"), console)
    out = _ANSI.sub("", console.file.getvalue())

    assert rc == EXIT_ERROR
    assert "doesn't exist" in out
    assert "wp proj -F" in out
    assert not gone.exists()


def test_nav_force_declined_leaves_nothing_behind(tmp_path, monkeypatch):
    console = _color_console()
    gone = tmp_path / "gone"
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(gone)}, default=None))
    monkeypatch.setattr("waypoint.commands.nav.confirm_create", lambda target: False)

    rc = _nav(NavCmd(alias="proj", force=True), console)

    assert rc == EXIT_ERROR
    assert not gone.exists()


def test_nav_force_accepted_creates_dir_and_navigates(tmp_path, monkeypatch, capsys):
    console = _color_console()
    gone = tmp_path / "gone"
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(gone)}, default=None))
    monkeypatch.setattr("waypoint.commands.nav.confirm_create", lambda target: True)

    rc = _nav(NavCmd(alias="proj", force=True), console)
    capsys.readouterr()

    assert rc == EXIT_OK
    assert gone.is_dir()
    assert "Created" in _ANSI.sub("", console.file.getvalue())


def test_nav_force_skips_prompt_when_dir_already_exists(tmp_path, monkeypatch, capsys):
    """-F must still hand the target back when there is nothing to create, because
    the wrapper runs it live and cannot read the path off stdout."""
    console = _color_console()
    target = tmp_path / "there"
    target.mkdir()
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(target)}, default=None))

    def boom(_target):
        raise AssertionError("must not prompt when the directory already exists")

    monkeypatch.setattr("waypoint.commands.nav.confirm_create", boom)

    rc = _nav(NavCmd(alias="proj", force=True), console)
    out = capsys.readouterr().out

    assert rc == EXIT_OK
    assert out.strip() == str(target)


def test_nav_force_hands_target_via_side_channel(tmp_path, monkeypatch):
    """With WP_NAV_OUT set, the path goes to the file and NOT to stdout -- stdout
    would otherwise carry a bare path the live wrapper cannot capture."""
    console = _color_console()
    nav_out = tmp_path / "nav.txt"
    monkeypatch.setenv(NAV_OUT_ENV, str(nav_out))
    target = tmp_path / "there"
    target.mkdir()
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(target)}, default=None))

    rc = _nav(NavCmd(alias="proj", force=True), console)

    assert rc == EXIT_OK
    assert nav_out.read_text(encoding="utf-8") == str(target)
    assert console.file.getvalue() == ""


def test_plain_nav_ignores_side_channel_when_unset(tmp_path, monkeypatch, capsys):
    """Without WP_NAV_OUT the stdout cd protocol must be unchanged: exactly one line."""
    console = _color_console()
    monkeypatch.delenv(NAV_OUT_ENV, raising=False)
    target = tmp_path / "there"
    target.mkdir()
    store.save_bookmarks(store.Bookmarks(bookmarks={"proj": str(target)}, default=None))

    rc = _nav(NavCmd(alias="proj"), console)
    out = capsys.readouterr().out

    assert rc == EXIT_OK
    assert out.splitlines() == [str(target)]
