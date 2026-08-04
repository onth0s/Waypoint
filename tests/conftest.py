"""Shared fixtures for Waypoint tests."""

import pytest

from waypoint import store


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
