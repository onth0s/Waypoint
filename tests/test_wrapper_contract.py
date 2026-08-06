"""Contract tests between install.ps1 (PowerShell wrapper) and the Waypoint CLI."""

from __future__ import annotations

import re

from waypoint import cli, store
from waypoint.store import PROJECT_DIR


def test_record_history_cli_behavior(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WP_HOME", str(tmp_path / "data"))
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)

    d1 = tmp_path / "d1"
    d1.mkdir()

    # 1. Records a valid dir
    rc = cli.main(["_record_history", str(d1)])
    out = capsys.readouterr()
    assert rc == 0
    assert out.out == ""  # Never prints to stdout
    assert store.load_history() == [str(d1)]

    # 2. Dedupes consecutive identical origins
    rc = cli.main(["_record_history", str(d1)])
    capsys.readouterr()
    assert rc == 0
    assert store.load_history() == [str(d1)]

    # 3. Ignores non-directory
    rc = cli.main(["_record_history", str(tmp_path / "nonexistent")])
    capsys.readouterr()
    assert rc == 0
    assert store.load_history() == [str(d1)]

    # 4. Usage error if no arg provided
    rc = cli.main(["_record_history"])
    capsys.readouterr()
    assert rc == 2


def test_interactive_commands_list_synced_with_install_ps1():
    """Assert $interactiveCmds in install.ps1 matches Python-side Prompt usage."""
    install_ps1_path = PROJECT_DIR / "install.ps1"
    text = install_ps1_path.read_text(encoding="utf-8")

    match = re.search(r"\$interactiveCmds\s*=\s*@\((.*?)\)", text)
    assert match is not None, "Could not find $interactiveCmds in install.ps1"

    raw_cmds = match.group(1)
    extracted_cmds = set(re.findall(r"['\"](.*?)['\"]", raw_cmds))

    # Today: only `add` invokes Prompt.ask / prompt_name
    expected_cmds = {"add"}
    assert extracted_cmds == expected_cmds, (
        f"$interactiveCmds in install.ps1 is {extracted_cmds}, "
        f"expected {expected_cmds}"
    )


def test_install_ps1_tracks_both_before_and_current_dir():
    """The wrapper must record the dir left AND the dir arrived at, so the
    persistent stack top is always the current dir (cross-tab `wp u 0`)."""
    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")
    calls = re.findall(r"_record_history\s+`\$(\w+)", text)
    assert calls == ["before", "current"], f"_record_history calls: {calls}"


def test_install_ps1_defines_no_space_cd_shortcuts():
    r"""The no-space cd shortcuts (cd.., cd~, cd\) are single tokens that
    PowerShell resolves to native Set-Location, bypassing the cd alias. The
    wrapper must define same-named functions that route through
    Set-WaypointLocation so they too feed the persistent history."""
    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")
    for fn in (
        "function global:cd.. { Set-WaypointLocation .. }",
        "function global:cd~ { Set-WaypointLocation ~ }",
        r"function global:cd\ { Set-WaypointLocation \ }",
    ):
        assert fn in text, f"missing in install.ps1: {fn}"


def test_install_ps1_waypoint_functions_are_global():
    """Block functions must be global:-prefixed so `uprof` (which dot-sources
    the profile from inside a function scope) actually re-applies them. A
    plain `function wp` defined in uprof's scope is discarded on return and
    the session silently keeps the stale startup copy."""
    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")
    for fn in (
        "function global:Set-WaypointLocation {",
        "function global:cdh {",
        "function global:wp {",
    ):
        assert fn in text, f"missing in install.ps1: {fn}"


def test_install_ps1_updates_existing_block_in_place():
    """install.ps1 must find an existing Waypoint block across the known
    profiles and replace it there, instead of appending a second block that a
    dot-source chain (pwsh -> WindowsPowerShell) would shadow."""
    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")

    assert "WindowsPowerShell\\Microsoft.PowerShell_profile.ps1" in text
    assert "foreach ($Candidate in $KnownProfiles)" in text
    assert "Test-Path -LiteralPath $Candidate" in text
    # Detection must match the legacy marker too ("file saved as UTF-8"),
    # not just the current ASCII-only text, or old blocks are missed.
    assert 'MarkerAny = "# Waypoint - path bookmark CLI ("' in text
    assert "Escape($MarkerAny)" in text
    # The known-profile search must come before the CurrentUserAllHosts default.
    search_pos = text.index("foreach ($Candidate in $KnownProfiles)")
    default_pos = text.index("$PROFILE.CurrentUserAllHosts")
    assert search_pos < default_pos
