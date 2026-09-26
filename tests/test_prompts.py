"""Interactive prompt tests: the [y/N] rendering and cancel plumbing."""

from __future__ import annotations

import pytest
from rich.console import Console

from waypoint.prompts import _Cancelled, confirm_create


def _recording_input(monkeypatch, reply: str) -> list[str]:
    """Replace Console.input, record the rendered prompt, return `reply`."""
    seen: list[str] = []

    def fake_input(self, prompt="", *args, **kwargs):
        seen.append(str(prompt))
        return reply

    monkeypatch.setattr(Console, "input", fake_input, raising=True)
    return seen


def test_confirm_create_renders_conventional_yes_no(monkeypatch):
    """rich's stock Confirm renders a flat "[y/n]" then repeats "(n)". The
    create prompt must read "[y/N]:" and nothing more."""
    seen = _recording_input(monkeypatch, "n")

    assert confirm_create("C:/dev/daemon_tests") is False
    assert seen == ["Create C:/dev/daemon_tests? [y/N]: "]


def test_confirm_create_escapes_bracketed_path(monkeypatch):
    """validate_alias permits brackets, and a path may contain them. They must
    survive as text rather than being parsed as markup."""
    seen = _recording_input(monkeypatch, "n")

    assert confirm_create("C:/dev/[draft]") is False
    assert "[draft]" in seen[0]


@pytest.mark.parametrize("reply", ["y", "Y"])
def test_confirm_create_accepts_both_cases(monkeypatch, reply):
    _recording_input(monkeypatch, reply)
    assert confirm_create("C:/dev/x") is True


@pytest.mark.parametrize("reply", ["n", "N"])
def test_confirm_create_declines_both_cases(monkeypatch, reply):
    _recording_input(monkeypatch, reply)
    assert confirm_create("C:/dev/x") is False


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_confirm_create_abort_raises_cancelled(monkeypatch, exc):
    """EOF / Ctrl+C reuse the existing _Cancelled plumbing, which cli turns into
    a "Cancelled." message and a non-zero exit."""

    def boom(self, prompt="", *args, **kwargs):
        raise exc

    monkeypatch.setattr(Console, "input", boom, raising=True)
    with pytest.raises(_Cancelled):
        confirm_create("C:/dev/x")


def test_yes_no_prompt_is_ascii_only(monkeypatch):
    """AGENTS.md: the wp wrapper pipes stdout, so Python encodes it with cp1252.
    Any non-ASCII in a prompt crashes with UnicodeEncodeError."""
    seen = _recording_input(monkeypatch, "n")
    confirm_create("C:/dev/daemon_tests")
    assert seen[0].isascii(), f"non-ASCII in prompt: {seen[0]!r}"
