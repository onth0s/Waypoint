"""Shared fixtures for Waypoint tests."""

import shutil
import subprocess
import sys

import pytest

from waypoint import store


def pytest_sessionstart(session):
    """Gate the whole run on a clean lint, so `pytest` doubles as the check."""
    if shutil.which("ruff") is None:
        pytest.exit("ruff not installed; run: pip install -e .[dev]", returncode=2)
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "."])
    if result.returncode != 0:
        pytest.exit("ruff check failed", returncode=result.returncode)


@pytest.fixture(autouse=True)
def isolate_project_dir_and_env(monkeypatch, tmp_path):
    """Automatically isolate PROJECT_DIR and WP_HOME for every test session."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    monkeypatch.setenv("WP_HOME", str(data_dir))


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
