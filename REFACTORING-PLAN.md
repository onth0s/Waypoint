# Waypoint — Code Audit & Refactoring Plan

## Audit Summary

**Codebase:** 1,290 lines Python across 4 source modules + 3 test modules (104 tests, all passing).
**Maturity:** Early-stage local CLI tool with clean initial design, strong test coverage, but zero project infrastructure.

### Health Scorecard

| Area | Grade | Notes |
|------|-------|-------|
| Architecture | A- | Clean 3-layer separation (resolver / store / cli) |
| Test coverage | A | 104 tests, full isolation via tmp_path + monkeypatch |
| Type annotations | A | Comprehensive, modern Python 3.10+ syntax |
| Code duplication | D | 5x identical "set temp slot" block; `_default` duplicates `_set` |
| Module sizing | D | `cli.py` is a 390-line god module with 5+ responsibilities |
| Magic values | D | 8x `"temp"`, 35x raw exit codes, 14x hardcoded rich markup |
| Packaging | F | No pyproject.toml, no pinned deps, no entry point |
| Linting/formatting | F | No config committed (code is clean by convention only) |
| CI/CD | F | Nonexistent |
| Git hygiene | C | 6 uncommitted files, line-ending warnings, no .gitattributes |

### Issues Found (Ranked by Severity)

| # | Severity | Issue | Location |
|---|----------|-------|----------|
| 1 | **HIGH** | `cli.py` god module — 390 lines, 13 functions, 5 responsibilities | `cli.py` |
| 2 | **HIGH** | 5x copy-pasted "set temp slot" block (6 lines each) | `cli.py:263-267, 282-286, 294-298, 311-315` |
| 3 | **HIGH** | `_default()` is a strict subset of `_set()` — duplicated logic | `cli.py:248-269` vs `cli.py:272-317` |
| 4 | **MEDIUM** | `UsageError` handling duplicated in `main()` (two identical try/except blocks) | `cli.py:52-55` and `cli.py:61-64` |
| 5 | **MEDIUM** | Magic string `"temp"` used 8x with no named constant | `cli.py` throughout |
| 6 | **MEDIUM** | Raw exit codes `0/1/2` used 35x as bare integers | `cli.py` throughout |
| 7 | **MEDIUM** | Hardcoded `[bold red]Error:[/bold red]` markup 14x | `cli.py` throughout |
| 8 | **MEDIUM** | Broad `except Exception:` swallows all errors in clipboard access | `cli.py:168` |
| 9 | **MEDIUM** | `_open()` computes `app` label from `kind` in 3 places | `cli.py:350, 354, 357` |
| 10 | **MEDIUM** | `_prompt_name()` — 4 levels of nesting, two try/except blocks | `cli.py:180-211` |
| 11 | **MEDIUM** | No `pyproject.toml` — no packaging, no pinned deps, no entry point | Project root |
| 12 | **MEDIUM** | `sys.path.insert()` hack + `noqa: E402` in `__main__.py` | `__main__.py:9-10` |
| 13 | **LOW** | Inconsistent arrow character: `→` vs `->` | `cli.py:160,266` vs `cli.py:285,297,314` |
| 14 | **LOW** | Misleading `# unreachable` comment on defense-in-depth line | `cli.py:89` |
| 15 | **LOW** | `load_config()` returns unparameterized `dict` | `store.py:40` |
| 16 | **LOW** | No `.gitattributes` — LF/CRLF warnings on every commit | Project root |
| 17 | **LOW** | `config.yaml` and `install.ps1` are tracked but machine-specific | `.gitignore` gap |

---

## Refactoring Plan — 6 Sequential Phases

Each phase is independently committable and testable. Run `pytest` after every phase to confirm zero regressions.

---

### Phase 0: Pre-flight Hygiene

**Goal:** Fix infrastructure before touching code. Every subsequent phase builds on a clean baseline.

**Step 0.1 — Add `.gitattributes`**
Create `Waypoint/.gitattributes`:
```
* text=auto eol=lf
```
Then renormalize: `git add --renormalize .` and commit. This eliminates the LF/CRLF warnings.

**Step 0.2 — Add `pyproject.toml`**
Create `Waypoint/pyproject.toml`:
```toml
[project]
name = "waypoint"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "rich>=13.0",
    "pyperclip>=1.8",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
wp = "waypoint.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 0.3 — Add linting config to `pyproject.toml`**
```toml
[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.10"
strict = true
```

**Step 0.4 — Pin dependencies in `install.ps1`**
Change the pip install line to use version constraints from pyproject.toml, or reference the project itself:
```powershell
python -m pip install -e "$RepoDir[dev]"
```

**Step 0.5 — Update `.gitignore`**
Add `.mypy_cache/` (already present), add `*.egg-info/` (already present), ensure `config.yaml` is NOT gitignored (it's project-level, not machine-specific — correct as-is).

**Verification:** `pytest` passes. `ruff check .` runs clean (or with only expected findings). `.gitattributes` eliminates line-ending warnings.

---

### Phase 1: Extract Constants and Output Helpers

**Goal:** Eliminate all magic values and hardcoded markup strings. This is the foundation for Phase 2's module split.

**Step 1.1 — Create `waypoint/constants.py`**
New file with all shared constants:
```python
"""Shared constants for the Waypoint CLI."""

# Bookmark names
TEMP_SLOT = "temp"
DEFAULT_BOOKMARK = "wp"

# Exit codes
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

# Reserved keywords (imported by resolver.py)
# Kept in resolver.py for co-location with the parser that uses them.
```

**Step 1.2 — Create `waypoint/output.py`**
New file with reusable output helpers:
```python
"""Formatted output helpers for the Waypoint CLI."""

from __future__ import annotations
from rich.console import Console

def err(console: Console, msg: str) -> None:
    """Print a red error line."""
    console.print(f"[bold red]Error:[/bold red] {msg}")

def ok(console: Console, msg: str) -> None:
    """Print a green success line."""
    console.print(f"[bold green]{msg}[/bold green]")

def warn(console: Console, msg: str) -> None:
    """Print a yellow warning line."""
    console.print(f"[yellow]Warning:[/yellow] {msg}")

def hint(console: Console, msg: str) -> None:
    """Print an informational hint (e.g. 'Run wp ls to see bookmarks')."""
    console.print(msg)
```

**Step 1.3 — Replace magic values in `cli.py`**
- Replace all `"temp"` with `TEMP_SLOT`
- Replace all `return 0/1/2` with `return EXIT_OK/EXIT_ERROR/EXIT_USAGE`
- Replace all `[bold red]Error:[/bold red]` with `err(console, ...)`
- Replace all `[bold green]...[/bold green]` with `ok(console, ...)`
- Replace all `[yellow]Warning:[/yellow]` with `warn(console, ...)`

**Step 1.4 — Standardize arrow character**
Pick one style (recommend `→` — it's already used in `_add` and `_default`) and replace all `->` arrows with `→` in `cli.py`.

**Step 1.5 — Narrow the broad exception in `clipboard_path()`**
Replace `except Exception:` with a more specific catch. Pyperclip raises `pyperclip.PyperclipException` (which inherits from `Exception`), plus platform-specific `OSError`/`RuntimeError`. The safest narrow catch:
```python
except (pyperclip.PyperclipException, OSError, RuntimeError):
    return None
```

**Step 1.6 — Fix `_open()` duplicate `app` computation**
Compute `app` once at the top of the function:
```python
app = "Explorer" if kind == "explorer" else "VS Code"
exe = "explorer" if kind == "explorer" else "code"
```

**Step 1.7 — Fix misleading `# unreachable` comment**
Change to `# safety net for future command kinds`.

**Verification:** `pytest` passes. All output formatting is identical. No behavioral changes.

---

### Phase 2: Split `cli.py` Into Modules

**Goal:** Break the god module into focused, single-responsibility modules. This is the highest-impact structural change.

**Step 2.1 — Extract `waypoint/commands.py`**
Move all command handler functions out of `cli.py`:
- `_nav`, `_default_target`, `_require_dir` → navigation
- `_add`, `clipboard_path`, `_prompt_name`, `_rm`, `_ls` → bookmark CRUD
- `_default`, `_set` → default management
- `_config` → settings
- `_open` → external programs
- `_help` → help text

Each handler gets `console: Console` as a parameter (already does). The new file imports from `store`, `resolver`, `output`, `constants`.

**Step 2.2 — Extract `waypoint/prompts.py`**
Move interactive prompting logic:
- `_prompt_name()` — the complex while/try/except collision handler
- Any future interactive prompts

**Step 2.3 — Slim down `cli.py` to pure dispatch**
After extraction, `cli.py` becomes ~60-80 lines:
- `main()` — console setup, top-level error handling
- `dispatch()` — if/elif routing to imported handlers
- `_Cancelled` exception class

**Step 2.4 — Update imports**
All test files import from `cli` — they should continue to work because `cli.py` re-exports or the tests import specific functions. Check `test_cli.py` line 11: `from waypoint import cli, store` — this still works because `cli` module still has `main()`.

**Verification:** `pytest` passes with zero changes to test files. Import graph remains acyclic.

---

### Phase 3: Eliminate Code Duplication

**Goal:** Remove the 5x duplicate "set temp slot" block and the `_default`/`_set` overlap.

**Step 3.1 — Extract `_set_temp_slot()` helper**
In `commands.py` (or `cli.py` depending on where it lands), create:
```python
def _set_temp_slot(target: str, b: store.Bookmarks, console: Console) -> int:
    """Point the default at a directory via the temp slot. Returns exit code."""
    if not os.path.isdir(target):
        err(console, f"not a directory: {target}")
        return EXIT_ERROR
    b.bookmarks[TEMP_SLOT] = target
    b.default = TEMP_SLOT
    store.save_bookmarks(b)
    ok(console, f"Default is now {TEMP_SLOT} → {target}")
    return EXIT_OK
```

**Step 3.2 — Refactor `_set()` to use the helper**
The 4 branches in `_set()` that set the temp slot all become single calls to `_set_temp_slot()`. The alias branch stays separate (it doesn't use the temp slot).

**Step 3.3 — Refactor `_default()` to delegate to `_set()`**
`_default` with a path argument is identical to `_set` with a path argument. Make `_default` call `_set` internally:
```python
def _default(cmd, console):
    arg = cmd.args[0]
    b = store.load_bookmarks()
    if arg in b.bookmarks:
        b.default = arg
        store.save_bookmarks(b)
        ok(console, f"Default is now {arg}")
        return EXIT_OK
    if looks_like_path(arg):
        return _set_temp_slot(os.path.abspath(os.path.expanduser(arg)), b, console)
    err(console, f"No bookmark {arg!r}.")
    return EXIT_ERROR
```

**Step 3.4 — Merge duplicate `UsageError` handling in `main()`**
Collapse the two try/except blocks into one:
```python
try:
    cmd = parse_args(args)
    return dispatch(cmd, console)
except _Cancelled:
    console.print("Cancelled.")
    return EXIT_ERROR
except UsageError as e:
    err(console, e)
    console.print("Run [bold]wp help[/bold] for usage.")
    return EXIT_USAGE
except store.StoreError as e:
    err(console, e)
    return EXIT_ERROR
```

**Step 3.5 — Flatten `_prompt_name()`**
Extract the collision-handling logic into a sub-function to reduce nesting from 4 to 2 levels:
```python
def _resolve_collision(name: str, b: Bookmarks, console: Console) -> str | None:
    """Handle the 'already exists' prompt. Returns new name, None to re-prompt, or raises _Cancelled."""
    ...
```

**Verification:** `pytest` passes. Output for every command is byte-identical (or character-identical modulo `→` normalization from Phase 1).

---

### Phase 4: Type Safety and Store Improvements

**Goal:** Tighten types, improve store robustness, and add missing error handling.

**Step 4.1 — Parameterize `load_config()` return type**
```python
def load_config() -> dict[str, str | None]:
```

**Step 4.2 — Add a `Config` dataclass**
Replace the raw dict return with a typed structure:
```python
@dataclass
class Config:
    home: str | None
```
Update `load_config() -> Config`, `save_config_home()`, and `data_dir()` to use it.

**Step 4.3 — Add `OSError` catch in `_open()`**
```python
except (FileNotFoundError, OSError) as e:
    err(console, f"{app} not found on PATH." if isinstance(e, FileNotFoundError) else str(e))
    return EXIT_ERROR
```

**Step 4.4 — Add type hints to `Command.args`**
The `args: list` field is intentionally loosely typed (different shapes per command kind). Document this clearly:
```python
@dataclass
class Command:
    kind: str  # nav | add | rm | ls | default | set | config | help | explorer | code
    args: list  # Shape varies by kind — see parse_args docstring.
```

**Step 4.5 — Add a `__all__` to each module**
Explicit public API for each module to clarify what's importable:
```python
# store.py
__all__ = ["Bookmarks", "StoreError", "data_dir", "load_bookmarks", "save_bookmarks", ...]
```

**Verification:** `pytest` passes. `mypy --strict waypoint/` reports no new errors (or only expected ones from pyperclip's stubs).

---

### Phase 5: Testing and CI Infrastructure

**Goal:** Formalize testing, add coverage measurement, set up CI.

**Step 5.1 — Add `pytest-cov` to dev dependencies**
Update `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]
```

**Step 5.2 — Add coverage configuration to `pyproject.toml`**
```toml
[tool.coverage.run]
source = ["waypoint"]

[tool.coverage.report]
show_missing = true
fail_under = 90
```

**Step 5.3 — Run coverage baseline**
```bash
pytest --cov --cov-report=term-missing
```
Document the baseline coverage percentage in the README or a `COVERAGE.md`.

**Step 5.4 — Add edge-case tests**
New tests to fill coverage gaps:
- `test_config.py` — dedicated config tests (currently only 3 in `test_cli.py`)
- `test_open_missing_exe.py` — test `_open()` when exe is not on PATH (currently mocked out)
- `test_clipboard.py` — dedicated clipboard integration tests
- Test `wp config home` with invalid paths
- Test `wp add` with clipboard returning a file (tests already exist at line 473, but add more edge cases)

**Step 5.5 — Add GitHub Actions CI**
Create `.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install -e ".[dev]"
      - run: pytest --cov --cov-report=term-missing
```

**Step 5.6 — Add ruff to CI**
```yaml
      - run: ruff check .
      - run: ruff format --check .
```

**Verification:** CI passes on push. Coverage is ≥90%.

---

### Phase 6: Documentation and Release Prep

**Goal:** Update docs, clean up, prepare for first tagged release.

**Step 6.1 — Update `README.md` file tree**
After Phase 2's module split, the file tree in the README is stale. Update it to reflect the new structure:
```
Waypoint/
├── README.md
├── AGENTS.md
├── pyproject.toml          ← NEW
├── .gitattributes           ← NEW
├── install.ps1
├── .gitignore
├── config.yaml
├── waypoint.yaml
├── waypoint/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py              ← slimmed (dispatch + main only)
│   ├── commands.py          ← NEW (all command handlers)
│   ├── prompts.py           ← NEW (interactive prompts)
│   ├── output.py            ← NEW (formatted output helpers)
│   ├── constants.py         ← NEW (shared constants)
│   ├── resolver.py
│   └── store.py
└── tests/
    ├── test_store.py
    ├── test_resolver.py
    └── test_cli.py
```

**Step 6.2 — Update `README.md` Stack section**
Add pyproject.toml, ruff, pytest-cov, mypy to the stack list.

**Step 6.3 — Update `install.ps1` to use `pip install -e .`**
Replace the manual `pip install rich pyperclip pyyaml` with:
```powershell
python -m pip install -e "$RepoDir[dev]"
```

**Step 6.4 — Add CHANGELOG.md**
Document the initial version and all refactoring changes.

**Step 6.5 — Tag v0.1.0**
```bash
git tag -a v0.1.0 -m "Waypoint v0.1.0: path-bookmark CLI with full refactoring"
```

**Verification:** README matches actual file structure. `install.ps1` works on fresh Python install. `pytest` passes. CI is green.

---

## Execution Order

```
Phase 0: Pre-flight Hygiene          (infrastructure, no code changes)
    ↓
Phase 1: Constants + Output Helpers  (new files, replace magic values in cli.py)
    ↓
Phase 2: Split cli.py                (structural refactor, no behavior change)
    ↓
Phase 3: Eliminate Duplication       (extract helpers, merge _default/_set)
    ↓
Phase 4: Type Safety + Store         (tighten types, add error handling)
    ↓
Phase 5: Testing + CI                (coverage, GitHub Actions)
    ↓
Phase 6: Documentation + Release     (README, install.ps1, tag)
```

**Critical rule:** Run `pytest` after every phase. Every phase must be a zero-regression commit.

---

## Estimated Impact

| Metric | Before | After |
|--------|--------|-------|
| `cli.py` lines | 390 | ~70 (dispatch + main) |
| `commands.py` lines | — | ~200 |
| Duplicate blocks | 5 | 0 |
| Magic string `"temp"` | 8x raw | 1x constant |
| Raw exit codes | 35x `0/1/2` | 35x `EXIT_OK/EXIT_ERROR/EXIT_USAGE` |
| Hardcoded markup | 14x inline | 0 (via output helpers) |
| Source modules | 4 | 8 (all focused) |
| Linting | None | ruff + mypy strict |
| CI | None | GitHub Actions |
| Coverage | Unknown | ≥90% enforced |
