"""Store tests: round-trip, seeding, resolution order, corruption.

Every test isolates the store from the real config.yaml/waypoint.yaml by
monkeypatching store.PROJECT_DIR and setting WP_HOME to a tmp path.
"""

from pathlib import Path

import pytest
import yaml

from waypoint import store


def _isolate(monkeypatch, tmp_path, home=None):
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    if home is not None:
        monkeypatch.setenv("WP_HOME", str(home))


def test_roundtrip(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    b = store.Bookmarks(bookmarks={"dev": r"C:\dev", "web": r"C:\web"}, default="dev")
    store.save_bookmarks(b)
    assert store.load_bookmarks() == b


def test_seeds_on_first_load(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    b = store.load_bookmarks()
    assert b == store.Bookmarks(bookmarks={"wp": str(store.PROJECT_DIR)}, default="wp")
    assert (tmp_path / "data" / "waypoint.yaml").is_file()


def test_existing_file_not_reseeded(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    data = tmp_path / "data"
    data.mkdir()
    (data / "waypoint.yaml").write_text("bookmarks: {}\ndefault: null\n", encoding="utf-8")
    assert store.load_bookmarks() == store.Bookmarks(bookmarks={}, default=None)


def test_resolution_order(monkeypatch, tmp_path):
    monkeypatch.delenv("WP_HOME", raising=False)  # outer shell may have it set
    project = tmp_path / "proj"
    cfg_home = tmp_path / "cfg"
    env_home = tmp_path / "env"
    project.mkdir()
    (project / "config.yaml").write_text(
        yaml.safe_dump({"home": str(cfg_home)}), encoding="utf-8"
    )
    monkeypatch.setattr(store, "PROJECT_DIR", project)

    assert store.data_dir() == cfg_home  # config home beats project dir

    monkeypatch.setenv("WP_HOME", str(env_home))
    assert store.data_dir() == env_home  # WP_HOME beats config home

    monkeypatch.delenv("WP_HOME")
    (project / "config.yaml").write_text(
        yaml.safe_dump({"home": None}), encoding="utf-8"
    )
    assert store.data_dir() == project  # project dir fallback


def test_corrupt_waypoint_raises(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    data = tmp_path / "data"
    data.mkdir()
    (data / "waypoint.yaml").write_text("bookmarks: [unclosed\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_bookmarks()


def test_non_dict_bookmarks_raises(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    data = tmp_path / "data"
    data.mkdir()
    (data / "waypoint.yaml").write_text("bookmarks: [1, 2]\ndefault: null\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_bookmarks()


def test_corrupt_config_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    (tmp_path / "config.yaml").write_text(": : bad\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_config()


def test_save_config_home_preserves_comment(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    store.save_config_home(str(tmp_path / "elsewhere"))
    cfg = store.load_config()
    assert Path(cfg["home"]) == tmp_path / "elsewhere"
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "Where waypoint.yaml lives" in text


def test_save_config_home_none_resets(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "PROJECT_DIR", tmp_path)
    store.save_config_home(str(tmp_path / "elsewhere"))
    store.save_config_home(None)
    assert store.load_config()["home"] is None
    text = (tmp_path / "config.yaml").read_text(encoding="utf-8")
    assert "home: null" in text
