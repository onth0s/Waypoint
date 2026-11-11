"""Shared fixtures for Waypoint tests."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from waypoint import store


@pytest.fixture(autouse=True)
def isolate_project_dir_and_env(monkeypatch, tmp_path):
    """Automatically isolate PROJECT_DIR, WP_CONFIG, APPDATA, and WP_HOME for every test session."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(exist_ok=True)
    cfg_file = tmp_path / "test_config" / "config.yaml"
    cfg_file.parent.mkdir(exist_ok=True)
    fake_appdata = tmp_path / "test_appdata"
    fake_appdata.mkdir(exist_ok=True)
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    monkeypatch.setenv("WP_HOME", str(data_dir))
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))
    monkeypatch.setenv("APPDATA", str(fake_appdata))

    yield

    # Test-level audit: if store.load_bookmarks() was called during the test and
    # yielded ONLY the hardcoded dummy seed bookmark ("wp" -> PROJECT_DIR), warn
    # that the test might be executing against an unisolated or unseeded store.
    resolved_path = store.bookmarks_path()
    if resolved_path.is_file():
        # Check if resolved to user profile directly (leak detection)
        user_home_store = Path.home() / ".waypoint"
        if user_home_store in resolved_path.parents or resolved_path.parent == user_home_store:
            warnings.warn(
                f"Test interacted directly with user store at {resolved_path}!",
                UserWarning,
                stacklevel=2,
            )
        try:
            b = store.load_bookmarks()
            is_dummy_seed = (
                list(b.bookmarks.keys()) == ["wp"]
                and b.bookmarks.get("wp") == str(store.PROJECT_DIR)
            )
            if is_dummy_seed:
                warnings.warn(
                    f"Test resolved to only default seed bookmark 'wp' -> {store.PROJECT_DIR}. "
                    "Verify test isolation or seed bookmarks explicitly.",
                    UserWarning,
                    stacklevel=2,
                )
        except Exception:
            pass


@pytest.fixture()
def isolated_store(monkeypatch, tmp_path):
    """Isolate store to a temp directory for the test."""
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def seeded_store(isolated_store):
    """Pre-seeded bookmarks for tests that need data."""
    from waypoint.store import Bookmarks, save_bookmarks

    b = Bookmarks(
        bookmarks={
            "dev": str(isolated_store / "dev"),
            "web": str(isolated_store / "web"),
        },
        default="dev",
    )
    (isolated_store / "dev").mkdir()
    (isolated_store / "web").mkdir()
    save_bookmarks(b)
    return b
