"""Read/write the two YAML data files: config.yaml (settings) and waypoint.yaml (bookmarks)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from waypoint.constants import UNDO_STACK

__all__ = [
    "Bookmarks",
    "StoreError",
    "BookmarkNotFoundError",
    "data_dir",
    "bookmarks_path",
    "history_path",
    "load_config",
    "save_config_home",
    "load_bookmarks",
    "save_bookmarks",
    "load_history",
    "save_history",
    "PROJECT_DIR",
]

# Discovered via Path(__file__).parent.parent from waypoint/__init__.py (README, Data section).
PROJECT_DIR = Path(__file__).resolve().parent.parent


class StoreError(Exception):
    """Raised when a data file is missing, malformed, or corrupt."""


class BookmarkNotFoundError(Exception):
    """Raised when a bookmark alias does not exist."""

    def __init__(self, alias: str) -> None:
        self.alias = alias
        super().__init__(f"No bookmark '{alias}'.")


@dataclass
class Bookmarks:
    bookmarks: dict[str, str]
    default: str | None


def data_dir() -> Path:
    """Where waypoint.yaml lives. Resolution order: WP_HOME -> config home -> project dir."""
    env = os.environ.get("WP_HOME")
    if env and env.strip():
        return Path(env).expanduser()
    home = load_config()["home"]
    if home:
        return Path(home).expanduser()
    return PROJECT_DIR


def bookmarks_path() -> Path:
    return data_dir() / "waypoint.yaml"


def history_path() -> Path:
    return data_dir() / "history.yaml"


def load_config() -> dict[str, str | None]:
    """Read config.yaml from the project dir. Missing file -> default settings."""
    path = PROJECT_DIR / "config.yaml"
    if not path.is_file():
        return {"home": None}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise StoreError("config.yaml is not valid YAML") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise StoreError("config.yaml is not valid YAML")
    return {"home": data.get("home")}


def save_config_home(path: str | None) -> None:
    """Set config.yaml's home key, preserving the file's explanatory comment.

    None resets to the documented default (`home: null` = project dir).
    """
    home = (
        "null"
        if path is None
        else yaml.safe_dump(
            os.path.abspath(os.path.expanduser(path)), default_style=None
        ).strip()
    )
    payload = (
        "# Where waypoint.yaml lives. Default: same dir as this config.\n"
        f"home: {home}\n"
    )
    _atomic_write(PROJECT_DIR / "config.yaml", payload)

def load_bookmarks() -> Bookmarks:
    """Read waypoint.yaml, creating and seeding it on first use."""
    path = bookmarks_path()
    if not path.is_file():
        seeded = Bookmarks(bookmarks={"wp": str(PROJECT_DIR)}, default="wp")
        save_bookmarks(seeded)
        return seeded
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise StoreError("waypoint.yaml is not valid YAML") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise StoreError("waypoint.yaml is not valid YAML")
    bookmarks = data.get("bookmarks", {})
    if not isinstance(bookmarks, dict) or not all(
        isinstance(alias, str) and isinstance(target, str)
        for alias, target in bookmarks.items()
    ):
        raise StoreError("waypoint.yaml `bookmarks` must be a mapping of alias to path")
    default = data.get("default")
    if default is not None and not isinstance(default, str):
        raise StoreError("waypoint.yaml `default` must be a bookmark alias")
    return Bookmarks(bookmarks=bookmarks, default=default)


def save_bookmarks(b: Bookmarks) -> None:
    """Write waypoint.yaml atomically (tmp file + replace, so a crash can't truncate it)."""
    path = bookmarks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(
        {"bookmarks": b.bookmarks, "default": b.default}, sort_keys=False
    )
    _atomic_write(path, payload)


def _atomic_write(path: Path, payload: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def load_history() -> list[str]:
    """Read the navigation-origin stack (oldest first). Missing file -> empty."""
    path = history_path()
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        raise StoreError("history.yaml is not valid YAML") from None
    if data is None:
        return []
    if not isinstance(data, list) or not all(isinstance(p, str) for p in data):
        raise StoreError("history.yaml must be a list of paths")
    return data


def save_history(entries: list[str]) -> None:
    """Write the navigation-origin stack, keeping only the newest UNDO_STACK."""
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = entries[-UNDO_STACK:]
    payload = yaml.safe_dump(kept, default_flow_style=False)
    _atomic_write(path, payload)
