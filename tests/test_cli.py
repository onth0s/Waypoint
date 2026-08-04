"""CLI tests: nav protocol, dispatch, exit codes, interactive flows.

Every test isolates the store: WP_HOME points into tmp_path and store.PROJECT_DIR
is pinned to tmp_path, so the real config.yaml/waypoint.yaml are never touched.
"""

import os
import subprocess
import types

from waypoint import cli, commands, store


def _run(monkeypatch, tmp_path, argv):
    monkeypatch.setenv("WP_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    return cli.main(argv)


def _is_nav_protocol_hit(out) -> bool:
    """True when stdout looks like a nav target: exactly one line, an existing dir."""
    lines = out.splitlines()
    return len(lines) == 1 and os.path.isdir(lines[0].strip())


def _add_dev(monkeypatch, tmp_path):
    target = tmp_path / "dev"
    target.mkdir()
    return target


# --- navigation -------------------------------------------------------------


def test_nav_prints_path_only(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()

    rc = _run(monkeypatch, tmp_path, ["dev"])
    out = capsys.readouterr()
    assert rc == 0
    assert len(out.out.splitlines()) == 1
    assert out.out.strip() == str(target)
    assert out.err == ""


def test_nav_unknown_alias(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["nope"])
    out = capsys.readouterr()
    assert rc == 1
    assert "No bookmark 'nope'" in out.out
    assert not _is_nav_protocol_hit(out.out)


def test_nav_no_default(monkeypatch, tmp_path, capsys):
    # Seed creates {wp, default=wp}; removing the default clears it.
    assert _run(monkeypatch, tmp_path, ["rm", "wp"]) == 0
    capsys.readouterr()

    rc = _run(monkeypatch, tmp_path, [])
    out = capsys.readouterr()
    assert rc == 1
    assert "No default bookmark" in out.out


def test_nav_missing_dir(monkeypatch, tmp_path, capsys):
    # Isolate FIRST: a direct save_bookmarks must never touch the real store.
    monkeypatch.setenv("WP_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    store.save_bookmarks(
        store.Bookmarks(bookmarks={"ghost": str(tmp_path / "gone")}, default=None)
    )
    rc = cli.main(["ghost"])
    out = capsys.readouterr()
    assert rc == 1
    assert "doesn't exist" in out.out


def test_wrapper_protocol_invariant(monkeypatch, tmp_path, capsys):
    """No non-nav command may print exactly one line that is an existing dir —
    the PowerShell wrapper would mis-cd on it."""
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)

    cases = [
        ["ls"],
        ["add", "web", str(target)],
        ["default", "dev"],
        ["default", "."],
        ["default", str(target)],
        ["set"],
        ["set", str(target)],
        ["set", "dev"],
        ["config"],
        ["config", "home", str(tmp_path / "home2")],
        ["help"],
        ["."],
        ["-vs"],
        ["rm", "web"],
        ["rm", "dev"],
    ]
    for argv in cases:
        rc = _run(monkeypatch, tmp_path, argv)
        out = capsys.readouterr()
        assert not (rc == 0 and _is_nav_protocol_hit(out.out)), f"protocol hit: {argv}"


# --- add --------------------------------------------------------------------


def test_add_two_arg(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    rc = _run(monkeypatch, tmp_path, ["add", "dev", str(target)])
    out = capsys.readouterr()
    assert rc == 0
    assert "Saved" in out.out
    assert store.load_bookmarks().bookmarks["dev"] == str(target)


def test_add_reserved_alias_is_usage_error(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["add", "add", str(tmp_path)])
    out = capsys.readouterr()
    assert rc == 2
    assert "reserved" in out.out


def test_add_nonexistent_target(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["add", "dev", str(tmp_path / "missing")])
    out = capsys.readouterr()
    assert rc == 1
    assert "not a directory" in out.out


def test_add_dot_prompts_for_name(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "here")
    rc = _run(monkeypatch, tmp_path, ["add", "."])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["here"] == str(tmp_path)


def test_add_path_like_single_arg_is_path_form(monkeypatch, tmp_path, capsys):
    target = tmp_path / "somewhere"
    target.mkdir()
    monkeypatch.setattr("builtins.input", lambda *a, **k: "s")
    rc = _run(monkeypatch, tmp_path, ["add", str(target)])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["s"] == str(target)


def test_add_clipboard_wins_over_cwd(monkeypatch, tmp_path, capsys):
    clip = tmp_path / "clip"
    clip.mkdir()
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: str(clip)))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "clip")
    rc = _run(monkeypatch, tmp_path, ["add"])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["clip"] == str(clip)


def test_add_clipboard_invalid_falls_back_to_cwd(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: "not a path"))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "cwd")
    rc = _run(monkeypatch, tmp_path, ["add"])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["cwd"] == str(tmp_path)


def test_add_clipboard_error_falls_back_to_cwd(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def boom():
        raise RuntimeError("no clipboard available")

    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=boom))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "cwd")
    rc = _run(monkeypatch, tmp_path, ["add"])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["cwd"] == str(tmp_path)


def test_add_collision_override(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr("builtins.input", lambda *a, **k: "override")
    rc = _run(monkeypatch, tmp_path, ["add", "dev", str(other)])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["dev"] == str(other)


def test_add_collision_rename(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    other = tmp_path / "other"
    other.mkdir()
    answers = iter(["rename", "dev2"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    rc = _run(monkeypatch, tmp_path, ["add", "dev", str(other)])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    # Rename saves the new bookmark under the fresh name; the pre-existing
    # `dev` bookmark is untouched (override is the only destructive option).
    assert b.bookmarks["dev2"] == str(other)
    assert b.bookmarks["dev"] == str(target)


def test_add_collision_cancel(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr("builtins.input", lambda *a, **k: "cancel")
    rc = _run(monkeypatch, tmp_path, ["add", "dev", str(other)])
    out = capsys.readouterr()
    assert rc == 1
    assert "Cancelled" in out.out
    assert store.load_bookmarks().bookmarks["dev"] == str(target)


# --- default / rm / config / open / help ------------------------------------


def test_default_flow(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()

    assert _run(monkeypatch, tmp_path, ["default", "dev"]) == 0
    capsys.readouterr()

    rc = _run(monkeypatch, tmp_path, [])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip() == str(target)

    rc = _run(monkeypatch, tmp_path, ["rm", "dev"])
    out = capsys.readouterr()
    assert rc == 0
    assert "Warning" in out.out
    assert store.load_bookmarks().default is None


def test_default_unknown_alias(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["default", "nope"])
    capsys.readouterr()
    assert rc == 1


def test_rm_unknown_alias(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["rm", "nope"])
    out = capsys.readouterr()
    assert rc == 1
    assert "No bookmark 'nope'" in out.out


def test_config_show_home_is_labeled(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["config"])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out.strip() == f"home: {tmp_path / 'data'}"


def test_config_set_home(monkeypatch, tmp_path, capsys):
    new_home = tmp_path / "newhome"
    rc = _run(monkeypatch, tmp_path, ["config", "home", str(new_home)])
    capsys.readouterr()
    assert rc == 0
    assert os.path.normpath(store.load_config()["home"]) == os.path.normpath(str(new_home))


def test_open_explorer_and_code(monkeypatch, tmp_path, capsys):
    calls = []
    monkeypatch.setattr(
        subprocess, "Popen", lambda argv, **k: calls.append(argv) or None
    )
    assert _run(monkeypatch, tmp_path, ["."]) == 0
    capsys.readouterr()
    assert _run(monkeypatch, tmp_path, ["-vs"]) == 0
    capsys.readouterr()
    # default bookmark is the seeded `wp` -> PROJECT_DIR (tmp_path)
    assert calls == [["explorer", str(tmp_path)], ["code", str(tmp_path)]]


def test_help_and_flags(monkeypatch, tmp_path, capsys):
    assert _run(monkeypatch, tmp_path, ["help"]) == 0
    assert "wp <alias>" in capsys.readouterr().out
    assert _run(monkeypatch, tmp_path, ["-h"]) == 0
    capsys.readouterr()
    assert _run(monkeypatch, tmp_path, ["-?"]) == 0
    capsys.readouterr()


def test_usage_error_exits_2(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["rm"])
    out = capsys.readouterr()
    assert rc == 2
    assert "usage" in out.out


def test_config_home_null_resets(monkeypatch, tmp_path, capsys):
    assert _run(monkeypatch, tmp_path, ["config", "home", str(tmp_path / "h2")]) == 0
    capsys.readouterr()
    rc = _run(monkeypatch, tmp_path, ["config", "home", "null"])
    out = capsys.readouterr()
    assert rc == 0
    assert store.load_config()["home"] is None
    assert "default" in out.out


def test_config_home_relative_path_resolves_to_absolute(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["config", "home", "../foo"])
    capsys.readouterr()
    assert rc == 0
    cfg = store.load_config()
    assert os.path.isabs(cfg["home"])


def test_config_home_null_case_insensitive(monkeypatch, tmp_path, capsys):
    assert _run(monkeypatch, tmp_path, ["config", "home", str(tmp_path / "h2")]) == 0
    capsys.readouterr()
    rc = _run(monkeypatch, tmp_path, ["config", "home", "NULL"])
    out = capsys.readouterr()
    assert rc == 0
    assert store.load_config()["home"] is None
    assert "default" in out.out


def test_rm_removes_default_shows_warning(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    assert _run(monkeypatch, tmp_path, ["default", "dev"]) == 0
    capsys.readouterr()
    rc = _run(monkeypatch, tmp_path, ["rm", "dev"])
    out = capsys.readouterr()
    assert rc == 0
    assert "Warning" in out.out
    assert store.load_bookmarks().default is None


def test_force_color_env_emits_ansi(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WP_FORCE_COLOR", "1")
    rc = _run(monkeypatch, tmp_path, ["help"])
    out = capsys.readouterr()
    assert rc == 0
    assert "\x1b[" in out.out


def test_unforced_output_stays_plain(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("WP_FORCE_COLOR", raising=False)
    rc = _run(monkeypatch, tmp_path, ["help"])
    out = capsys.readouterr()
    assert rc == 0
    assert "\x1b[" not in out.out


def test_default_dot_sets_temp_to_cwd(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    rc = _run(monkeypatch, tmp_path, ["default", "."])
    out = capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(tmp_path)
    assert "temp" in out.out


def test_default_path_creates_temp_slot(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    rc = _run(monkeypatch, tmp_path, ["default", str(target)])
    out = capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(target)
    assert "temp" in out.out


def test_default_missing_path_errors(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["default", str(tmp_path / "missing")])
    out = capsys.readouterr()
    assert rc == 1
    assert "not a directory" in out.out


def test_default_unknown_alias_still_errors(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["default", "nope"])
    out = capsys.readouterr()
    assert rc == 1
    assert "No bookmark" in out.out


def test_default_alias_keeps_working_after_temp(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    assert _run(monkeypatch, tmp_path, ["default", "."]) == 0
    capsys.readouterr()
    assert _run(monkeypatch, tmp_path, ["default", "dev"]) == 0
    capsys.readouterr()
    assert store.load_bookmarks().default == "dev"


# --- set ---------------------------------------------------------------------


def test_set_clipboard_wins(monkeypatch, tmp_path, capsys):
    clip = tmp_path / "clip"
    clip.mkdir()
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: str(clip)))
    rc = _run(monkeypatch, tmp_path, ["set"])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(clip)


def test_set_cwd_fallback(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: "not a path"))
    rc = _run(monkeypatch, tmp_path, ["set"])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(tmp_path)


def test_set_clipboard_error_falls_back(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    def boom():
        raise RuntimeError("no clipboard")

    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=boom))
    rc = _run(monkeypatch, tmp_path, ["set"])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(tmp_path)


def test_set_dot_ignores_clipboard(monkeypatch, tmp_path, capsys):
    clip = tmp_path / "clip"
    clip.mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: str(clip)))
    rc = _run(monkeypatch, tmp_path, ["set", "."])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(tmp_path)


def test_set_alias_form(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    assert _run(monkeypatch, tmp_path, ["add", "dev", str(target)]) == 0
    capsys.readouterr()
    rc = _run(monkeypatch, tmp_path, ["set", "dev"])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().default == "dev"


def test_set_path_form(monkeypatch, tmp_path, capsys):
    target = _add_dev(monkeypatch, tmp_path)
    rc = _run(monkeypatch, tmp_path, ["set", str(target)])
    capsys.readouterr()
    assert rc == 0
    b = store.load_bookmarks()
    assert b.default == "temp"
    assert b.bookmarks["temp"] == str(target)


def test_set_unknown_alias_errors(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["set", "nope"])
    out = capsys.readouterr()
    assert rc == 1
    assert "No bookmark" in out.out


def test_set_missing_path_errors(monkeypatch, tmp_path, capsys):
    rc = _run(monkeypatch, tmp_path, ["set", str(tmp_path / "missing")])
    out = capsys.readouterr()
    assert rc == 1
    assert "not a directory" in out.out


def test_add_clipboard_file_uses_parent(monkeypatch, tmp_path, capsys):
    f = tmp_path / "notes.txt"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr(commands, "pyperclip", types.SimpleNamespace(paste=lambda: str(f)))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "docs")
    rc = _run(monkeypatch, tmp_path, ["add"])
    capsys.readouterr()
    assert rc == 0
    assert store.load_bookmarks().bookmarks["docs"] == str(tmp_path)
