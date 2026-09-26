"""Contract tests between install.ps1 (PowerShell wrapper) and the Waypoint CLI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from waypoint import cli, store
from waypoint.store import PROJECT_DIR

# Resolved at import time, before the autouse fixture patches store.PROJECT_DIR,
# so this is the real checkout -- which is where install.ps1 and __main__.py live.
REPO = str(PROJECT_DIR)


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

    # `add` is the only command that prompts. -F deliberately does not -- the
    # flag is the consent -- but it does print a success line before navigating,
    # so it needs the live branch for the side channel, not for a prompt.
    expected_cmds = {"add"}
    assert extracted_cmds == expected_cmds, (
        f"$interactiveCmds in install.ps1 is {extracted_cmds}, "
        f"expected {expected_cmds}"
    )


def test_install_ps1_runs_force_flag_live_with_nav_side_channel():
    r"""`wp <alias> -F` reports the directory it created, so stdout is no longer a
    single bare path and the wrapper's cd discriminator cannot read it. -F
    therefore runs live and returns its target through the WP_NAV_OUT side
    channel rather than stdout."""
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


# --- end-to-end: the real wrapper, in a real child shell -----------------------
#
# The unit tests above can all pass while `wp <alias> -F` still hangs on the user,
# because the failure lives in the PowerShell wrapper, not in Python. Only a child
# process catches that: a function called with no param() block discards pipeline
# input, so the answer must arrive via the child's real stdin instead.

PWSH = shutil.which("pwsh") or shutil.which("powershell")
needs_pwsh = pytest.mark.skipif(PWSH is None, reason="PowerShell not on PATH")

# Extracts and evaluates the wrapper straight from install.ps1 (never the user's
# profile, so a stale installed block cannot mask or fake a result), then calls it.
HARNESS = r"""
$ErrorActionPreference = 'Stop'
$src = Get-Content -LiteralPath '__REPO__\install.ps1' -Raw
$m = [regex]::Match($src, '(?s)\$Block = @"(.*?)\r?\n"@')
if (-not $m.Success) { throw 'could not extract $Block' }
$assign = "`$RepoDir = `"__REPO__`"`n" + '$Block = @"' + $m.Groups[1].Value + '"@'
Invoke-Expression $assign
Invoke-Expression $Block

Set-Location '__WORK__'
$missing = '__WORK__\_delete-me\daemon_tests'
Write-Output "MISSING_BEFORE=$( -not (Test-Path -LiteralPath $missing) )"

wp delmon -F

Write-Output "RC=$LASTEXITCODE"
Write-Output "TARGET_EXISTS=$(Test-Path -LiteralPath $missing)"
Write-Output "LOC=$((Get-Location).Path)"
"""


def _nav_out_files() -> set[Path]:
    """Temp files the wrapper's side channel could have left behind.

    Matches the wrapper's own naming -- 'wp_nav_' plus a 32-char guid -- so
    unrelated wp_nav_*.txt files cannot make this flaky.
    """
    import re as _re
    import tempfile

    pattern = _re.compile(r"^wp_nav_[0-9a-fA-F]{32}\.txt$")
    return {p for p in Path(tempfile.gettempdir()).glob("wp_nav_*") if pattern.match(p.name)}


def _run_wrapper(tmp_path):
    """Drive the real wp wrapper in a child PowerShell.

    stdin is left closed: -F must never prompt, and a wrapper that reintroduced a
    prompt would otherwise hang until the 120s timeout instead of failing.
    """
    work = tmp_path / "shell"
    work.mkdir()
    (work / "waypoint.yaml").write_text(
        yaml.safe_dump(
            {
                "bookmarks": {"delmon": str(work / "_delete-me" / "daemon_tests")},
                "default": None,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    script = tmp_path / "harness.ps1"
    script.write_text(
        HARNESS.replace("__REPO__", REPO).replace("__WORK__", str(work)),
        encoding="utf-8",
    )

    # WP_HOME pins the data dir; the child's cwd already has waypoint.yaml, which
    # takes precedence, so this only keeps history.yaml inside the fixture.
    env = {**os.environ, "WP_HOME": str(work)}
    env.pop("WP_NAV_OUT", None)
    return work, subprocess.run(
        [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        cwd=work,
        env=env,
        timeout=120,
    )


@needs_pwsh
def test_wrapper_force_creates_dir_and_lands_in_it(tmp_path):
    """`wp delmon -F`: no prompt, dir created, reported, and the shell lands inside.

    The cd is the whole point of the WP_NAV_OUT side channel -- -F prints a
    success line, so the bare path the wrapper would otherwise read off captured
    stdout is not there to be read.
    """
    work, proc = _run_wrapper(tmp_path)
    target = work / "_delete-me" / "daemon_tests"
    context = f"\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"

    assert "MISSING_BEFORE=True" in proc.stdout, context
    assert "[y/N]" not in proc.stdout, f"-F must not prompt{context}"
    assert f"Created delmon -> {target}" in proc.stdout, (
        f"creation not reported{context}"
    )
    assert "RC=0" in proc.stdout, context
    assert target.is_dir(), f"directory not created{context}"
    assert "TARGET_EXISTS=True" in proc.stdout, context
    assert f"LOC={target}" in proc.stdout, f"wrapper did not cd into the new dir{context}"


@needs_pwsh
def test_wrapper_force_cleans_up_its_temp_file(tmp_path):
    """A leftover wp_nav_*.txt would accumulate in TEMP on every -F invocation.

    Diffed rather than globbed, so a stale file from an earlier run cannot fail
    this or mask a real leak.
    """
    before = _nav_out_files()
    _, proc = _run_wrapper(tmp_path)
    context = f"\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"

    leaked = _nav_out_files() - before
    assert not leaked, f"wrapper leaked side-channel temp file(s): {sorted(leaked)}{context}"


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
