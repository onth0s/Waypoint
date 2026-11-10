"""Read/write the three YAML data files: config.yaml (settings), waypoint.yaml
(bookmarks), and history.yaml (navigation history).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    msvcrt = None  # type: ignore[assignment]

import yaml

from waypoint.constants import UNDO_STACK, WaypointError

__all__ = [
    "Bookmarks",
    "StoreError",
    "BookmarkNotFoundError",
    "data_dir",
    "bookmarks_path",
    "history_path",
    "config_path",
    "load_config",
    "save_config_home",
    "load_bookmarks",
    "save_bookmarks",
    "load_history",
    "save_history",
    "transaction",
    "PROJECT_DIR",
]

# Discovered via Path(__file__).parent.parent from waypoint/__init__.py (README, Data section).
PROJECT_DIR = Path(__file__).resolve().parent.parent


class StoreError(WaypointError):
    """Raised when a data file is missing, malformed, or corrupt."""


class BookmarkNotFoundError(WaypointError):
    """Raised when a bookmark alias does not exist."""

    def __init__(self, alias: str) -> None:
        self.alias = alias
        super().__init__(f"No bookmark '{alias}'.")


@dataclass
class Bookmarks:
    bookmarks: dict[str, str]
    default: str | None
    _prev_default: str | None = None

    def set_default(self, alias: str) -> None:
        """Set a bookmark as default and clear any previously remembered default."""
        self.default = alias
        self._prev_default = None

    def remove(self, alias: str) -> bool:
        """Remove a bookmark.

        If it was default, remember it in _prev_default. Returns True if was default.
        """
        was_default = (self.default == alias)
        if alias in self.bookmarks:
            del self.bookmarks[alias]
        if was_default:
            self._prev_default = alias
            self.default = None
        return was_default

    def restore_default_if_readded(self, name: str) -> bool:
        """If there is no default and name matches _prev_default, restore default.

        Returns True if restored.
        """
        if self.default is None and self._prev_default == name:
            self.default = name
            self._prev_default = None
            return True
        return False


@contextmanager
def transaction(target_dir: Path | None = None, timeout: float = 1.0) -> Iterator[None]:
    """Cross-process lock guarding read-modify-write operations on the store."""
    lock_dir = target_dir or data_dir()
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = lock_dir / ".store.lock"

    try:
        fd = os.open(str(lock_file), os.O_RDWR | os.O_CREAT)
    except OSError:
        # Fall open if lock file cannot be opened (e.g. read-only environment)
        yield
        return

    start_time = time.monotonic()
    locked = False
    while time.monotonic() - start_time < timeout:
        try:
            if msvcrt is not None:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            locked = True
            break
        except (OSError, PermissionError):
            time.sleep(0.01)

    try:
        yield
    finally:
        if locked and msvcrt is not None:
            with suppress(OSError):
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        with suppress(OSError):
            os.close(fd)


def data_dir() -> Path:
    """Where waypoint.yaml and history.yaml live by default.

    Resolution order: WP_HOME -> config home -> ~/.waypoint.
    """
    env = os.environ.get("WP_HOME")
    if env and env.strip():
        return Path(env).expanduser()
    home = load_config()["home"]
    if home:
        return Path(home).expanduser()
    return Path.home() / ".waypoint"


def bookmarks_path() -> Path:
    return data_dir() / "waypoint.yaml"


def history_path() -> Path:
    return data_dir() / "history.yaml"


def config_path() -> Path:
    """Location of config.yaml.

    Resolution: WP_CONFIG env var > %APPDATA%/waypoint/config.yaml (or ~/.waypoint/config.yaml).
    If a legacy config.yaml exists in PROJECT_DIR and the new file does not, it is read as fallback.
    """
    env = os.environ.get("WP_CONFIG")
    if env and env.strip():
        return Path(env).expanduser()
    appdata = os.environ.get("APPDATA")
    if appdata and appdata.strip():
        target = Path(appdata) / "waypoint" / "config.yaml"
    else:
        target = Path.home() / ".waypoint" / "config.yaml"

    if not target.is_file():
        legacy = PROJECT_DIR / "config.yaml"
        if legacy.is_file():
            return legacy
    return target


def load_config() -> dict[str, str | None]:
    """Read config.yaml. Missing file -> default settings."""
    path = config_path()
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
    home = data.get("home")
    if home is not None and not isinstance(home, str):
        raise StoreError("config.yaml `home` must be a path string or null")
    return {"home": home}


def save_config_home(path: str | None) -> None:
    """Set config.yaml's home key, preserving the file's explanatory comment.

    None resets to the documented default (`home: null` = ~/.waypoint).
    """
    home = (
        "null"
        if path is None
        else yaml.safe_dump(
            os.path.abspath(os.path.expanduser(path)), default_style=None
        ).strip()
    )
    payload = (
        "# Where waypoint.yaml lives. Default: ~/.waypoint\n"
        f"home: {home}\n"
    )
    cfg_file = config_path()
    # If WP_CONFIG was not explicitly set and config_path returned legacy in PROJECT_DIR,
    # migrate write to preferred appdata location.
    if not os.environ.get("WP_CONFIG") and cfg_file == PROJECT_DIR / "config.yaml":
        appdata = os.environ.get("APPDATA")
        if appdata and appdata.strip():
            cfg_file = Path(appdata) / "waypoint" / "config.yaml"
        else:
            cfg_file = Path.home() / ".waypoint" / "config.yaml"
    _atomic_write(cfg_file, payload)


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
    prev_default = data.get("_prev_default")
    if prev_default is not None and not isinstance(prev_default, str):
        prev_default = None
    return Bookmarks(bookmarks=bookmarks, default=default, _prev_default=prev_default)


def save_bookmarks(b: Bookmarks) -> None:
    """Write waypoint.yaml atomically (tmp file + replace, so a crash can't truncate it)."""
    path = bookmarks_path()
    data: dict[str, object] = {"bookmarks": b.bookmarks, "default": b.default}
    if b._prev_default is not None:
        data["_prev_default"] = b._prev_default
    payload = yaml.safe_dump(data, sort_keys=False)
    _atomic_write(path, payload)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(
        dir=path.parent, prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())

        # On Windows, antivirus or search indexers can hold a transient lock on the file.
        # Retry briefly with backoff if PermissionError occurs.
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                os.replace(tmp_path_str, path)
                break
            except PermissionError as e:
                last_err = e
                if attempt < 3:
                    import time

                    time.sleep(0.015 * (2**attempt))
                else:
                    raise last_err from None
    except Exception:
        if os.path.exists(tmp_path_str):
            os.unlink(tmp_path_str)
        raise


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
    kept = entries[-UNDO_STACK:]
    payload = yaml.safe_dump(kept, default_flow_style=False)
    _atomic_write(path, payload)
