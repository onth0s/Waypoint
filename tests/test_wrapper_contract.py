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

    # 3. Records even non-existent dirs (stale entries filtered at read time)
    rc = cli.main(["_record_history", str(tmp_path / "nonexistent")])
    capsys.readouterr()
    assert rc == 0
    assert store.load_history() == [str(d1), str(tmp_path / "nonexistent")]

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

    # Today: only `add` invokes Prompt.ask / prompt_name as a *command*. The -F
    # nav flag also prompts, but it is a flag rather than a subcommand, so the
    # wrapper branches on it separately (see the force-flag test below).
    expected_cmds = {"add"}
    assert extracted_cmds == expected_cmds, (
        f"$interactiveCmds in install.ps1 is {extracted_cmds}, "
        f"expected {expected_cmds}"
    )


def test_install_ps1_runs_force_flag_live_with_nav_side_channel():
    r"""`wp <alias> -F` prompts to create a missing directory, so it must run live
    like `wp add` -- a captured stdout buffers the prompt and the user types blind.
    A live process cannot hand its path back over that captured stdout, so the
    wrapper needs the WP_NAV_OUT side channel to learn where to cd."""
    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")
    assert "`$force = `$args -contains '-F'" in text, "missing -F live detection"
    assert "`$force -or (`$args.Count -gt 0" in text, (
        "-F must be able to force the live branch on its own"
    )
    assert "`$env:WP_NAV_OUT = `$navOut" in text, "side channel is never exported"
    assert "Set-WaypointLocation -Literal `$target" in text, (
        "wrapper never cds to the handed-off target"
    )
    # The temp file must not outlive the call.
    assert "Remove-Item -LiteralPath `$navOut -Force" in text


def test_nav_side_channel_env_var_matches_install_ps1():
    """WP_NAV_OUT is a Python<->PowerShell contract. A rename on either side alone
    silently breaks the cd after `wp <alias> -F`, because the Python side would
    fall back to stdout and the live wrapper cannot read it."""
    from waypoint.commands.nav import NAV_OUT_ENV

    text = (PROJECT_DIR / "install.ps1").read_text(encoding="utf-8")
    assert NAV_OUT_ENV in text, (
        f"install.ps1 never references {NAV_OUT_ENV}; the -F handoff will not work"
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
