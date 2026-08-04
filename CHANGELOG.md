# Changelog

All notable changes to Waypoint are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/) conventions.

## [0.1.0] - 2026-08-04

### Added
- **Packaging**: `pyproject.toml` with pinned dependency floors (`rich>=13`, `pyperclip>=1.8`, `pyyaml>=6`), a `wp` console-script entry point, and `[project.optional-dependencies] dev` extras (mypy, pytest, ruff, types-PyYAML). `install.ps1` now installs via `pip install -e ".[dev]"`.
- **New modules** extracted from the old god-module `cli.py`:
  - `waypoint/commands.py` — all command handlers (navigation, bookmark CRUD, default management, settings, open, help).
  - `waypoint/prompts.py` — interactive prompting (name entry + collision handling).
  - `waypoint/constants.py` — named constants for the `temp` slot and exit codes.
  - `waypoint/output.py` — centralized rich markup helpers (`err`, `ok`, `warn`, `hint`).
- **`BookmarkNotFoundError`** in `waypoint/store.py` — a domain exception for missing aliases, handled centrally in `main()`.
- **`__all__` exports** on `store.py`, `resolver.py`, `output.py`, `constants.py` for an auditable public API.
- **`.gitattributes`** with `* text=auto eol=lf`; config.yaml untracked and gitignored (machine-specific home path).
- **Tests**: `tests/conftest.py` (shared `isolated_store` / `seeded_store` fixtures), `tests/test_constants.py`, `tests/test_output.py`, plus 3 new edge tests (relative `config home` path, case-insensitive `NULL`, default-removal warning). Suite grew 104 → 114.

### Changed
- `cli.py` slimmed from 390 lines (15 functions, 5 responsibilities) to pure dispatch + entry point.
- Duplicate "set temp slot" block (4 copies) collapsed into `_set_temp_slot()`; `_default()` and `_set()` share it.
- `_prompt_name()` nesting flattened from 4 to 2 levels via `_resolve_collision()`.
- Exit codes and the `"temp"` slot are named constants (`EXIT_OK`/`EXIT_ERROR`/`EXIT_USAGE`, `TEMP_SLOT`).
- Duplicate `UsageError` handling in `main()` merged into a single try/except.
- `clipboard_path()` narrowed from bare `except Exception` to `(OSError, RuntimeError)`.
- `_open()` computes the app label once instead of three times.
- Arrow character standardized to `\u2192` (`→`) in all user-facing output.
- `__main__.py` dropped its `sys.path` bootstrap hack; `python -m waypoint` now resolves via the installed package.
- `Command.args` typed as `list[str | None]`; `load_config()` typed as `dict[str, str | None]`.
- `dispatch()` takes a typed `Command`; structural-`None` invariants (`default`/`config` args, `b.default` after `_default_target()`) made explicit with `assert`s so the whole package passes `mypy --strict`.
- Misleading `# unreachable` comment corrected to a safety-net note.

### Fixed
- `_config()` relative-path home handling now resolves to an absolute path before saving (covered by new test).
- `data_dir()` path resolution robustness (documented; creation handled by the store's atomic writer).

### Removed
- `sys.path.insert` + `noqa: E402` workaround in `__main__.py`.
- Raw hardcoded rich markup from command handlers (centralized in `output.py`).
