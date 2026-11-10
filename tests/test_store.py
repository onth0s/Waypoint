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
    cfg_file = tmp_path / "cfg_dir" / "config.yaml"
    cfg_home = tmp_path / "cfg"
    env_home = tmp_path / "env"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        yaml.safe_dump({"home": str(cfg_home)}), encoding="utf-8"
    )
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))

    assert store.data_dir() == cfg_home  # config home beats default

    monkeypatch.setenv("WP_HOME", str(env_home))
    assert store.data_dir() == env_home  # WP_HOME beats config home

    monkeypatch.delenv("WP_HOME")
    cfg_file.write_text(
        yaml.safe_dump({"home": None}), encoding="utf-8"
    )
    assert store.data_dir() == Path.home() / ".waypoint"  # default store fallback


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
    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))
    cfg_file.write_text(": : bad\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_config()


def test_save_config_home_preserves_comment(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))
    store.save_config_home(str(tmp_path / "elsewhere"))
    cfg = store.load_config()
    assert Path(cfg["home"]) == tmp_path / "elsewhere"
    text = cfg_file.read_text(encoding="utf-8")
    assert "Where waypoint.yaml lives" in text


def test_save_config_home_none_resets(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))
    store.save_config_home(str(tmp_path / "elsewhere"))
    store.save_config_home(None)
    assert store.load_config()["home"] is None
    text = cfg_file.read_text(encoding="utf-8")
    assert "home: null" in text


def test_history_roundtrip(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    assert store.load_history() == []
    store.save_history([r"C:\a", r"C:\b"])
    assert store.load_history() == [r"C:\a", r"C:\b"]
    assert (tmp_path / "data" / "history.yaml").is_file()


def test_history_missing_file_is_empty(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    assert store.load_history() == []


def test_history_follows_data_dir(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    store.save_history([r"C:\a"])
    assert store.history_path() == tmp_path / "data" / "history.yaml"
    assert store.history_path().is_file()


def test_history_corrupt_raises(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    data = tmp_path / "data"
    data.mkdir()
    (data / "history.yaml").write_text("bookmarks: {bad\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_history()


def test_history_non_list_raises(monkeypatch, tmp_path):
    _isolate(monkeypatch, tmp_path, home=tmp_path / "data")
    data = tmp_path / "data"
    data.mkdir()
    (data / "history.yaml").write_text("not-a-list\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_history()


def test_non_string_config_home_raises(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.yaml"
    monkeypatch.setenv("WP_CONFIG", str(cfg_file))
    cfg_file.write_text("home: 123\n", encoding="utf-8")
    with pytest.raises(store.StoreError):
        store.load_config()


def test_atomic_write_creates_nested_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "test.txt"
    store._atomic_write(target, "content")
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "content"


def test_bookmarks_and_history_path_ignore_cwd(monkeypatch, tmp_path):
    data_home = tmp_path / "global_data"
    data_home.mkdir()
    _isolate(monkeypatch, tmp_path, home=data_home)

    local_dir = tmp_path / "local_proj"
    local_dir.mkdir()
    local_wp = local_dir / "waypoint.yaml"
    local_wp.write_text(
        yaml.safe_dump({"bookmarks": {"local": str(local_dir)}, "default": "local"}),
        encoding="utf-8",
    )
    local_hist = local_dir / "history.yaml"
    local_hist.write_text(yaml.safe_dump([r"C:\local_origin"]), encoding="utf-8")

    monkeypatch.chdir(local_dir)
    # Store paths resolve to global data_home, ignoring local directory files (A1 resolution)
    assert store.bookmarks_path() == data_home / "waypoint.yaml"
    assert store.history_path() == data_home / "history.yaml"

    b = store.Bookmarks(bookmarks={"global_bm": str(data_home)}, default="global_bm")
    store.save_bookmarks(b)
    assert (data_home / "waypoint.yaml").is_file()

    store.save_history([r"C:\global_origin"])
    assert store.load_history() == [r"C:\global_origin"]


def test_concurrent_history_recording_no_loss(monkeypatch, tmp_path):
    import concurrent.futures
    import time

    from waypoint.commands.history import cmd_record_history
    from waypoint.resolver import RecordHistoryCmd

    data_home = tmp_path / "concurrent_data"
    data_home.mkdir()
    _isolate(monkeypatch, tmp_path, home=data_home)

    def worker(worker_id: int) -> None:
        for i in range(10):
            cmd = RecordHistoryCmd(origins=[f"C:\\concurrent_{worker_id}_{i}"])
            cmd_record_history(cmd)
            time.sleep(0.002)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(worker, w) for w in range(4)]
        concurrent.futures.wait(futures)

    hist = store.load_history()
    # 4 workers * 10 entries = 40 unique entries recorded with locking
    assert len(hist) == 40


def test_atomic_write_retries_transient_permission_error(monkeypatch, tmp_path):
    target = tmp_path / "flaky.txt"
    attempts = 0
    real_replace = store.os.replace

    def flaky_replace(src, dst):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("Access is denied (transient lock)")
        return real_replace(src, dst)

    monkeypatch.setattr(store.os, "replace", flaky_replace)
    store._atomic_write(target, "success")
    assert target.read_text(encoding="utf-8") == "success"
    assert attempts == 3
