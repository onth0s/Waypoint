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
