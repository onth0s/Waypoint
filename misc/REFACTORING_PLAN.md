# REFACTORING_PLAN.md — Waypoint Codebase Audit & Sequential Refactor Plan

Run date: 2026-08-04 | Branch: `dev` | Baseline: 174 tests passing, ruff clean, mypy strict clean.

This document is the product of a full audit of the Waypoint codebase and the
refactoring plan that follows from it. **The plan MUST be executed sequentially:
finish every phase in order, and never start phase N+1 until phase N meets its
Definition of Done.** Phases are ordered so that behavior fixes land first
(cheapest while the code is fresh), typing/structure hardening second, docs last.

---

## Part 1 — Audit

### 1.1 Scope & ground truth

- Code: `waypoint/` (15 source files, ~34 KB), `install.ps1`, `pyproject.toml`.
- Tests: `tests/` (9 files, 174 tests).
- Spec: `README.md` is the sole ground truth (per `misc/INSPECTOR.md`).
- Verification state at audit time:
  - `python -m pytest -q` -> 174 passed
  - `python -m ruff check .` -> All checks passed
  - `python -m mypy waypoint` -> Success: no issues found in 15 source files

### 1.2 Architecture (as-built)

```
__main__.py -> cli.main() -> parse_args (resolver) -> dispatch (cli) -> handlers (commands/)
                                                     |-> store (YAML I/O, atomic writes)
                                                     |-> output / prompts / clipboard (services)
                                     install.ps1 (PowerShell wrapper) <-> CLI via:
                                       stdout protocol (single existing-path line = cd),
                                       WP_FORCE_COLOR env, `_record_history` hidden command
```

Strengths (do not refactor these away):

- Clean layering: constants -> services -> store -> resolver -> handlers -> cli.
- Atomic writes (`tmp` + `os.replace`) for all YAML files.
- Exit-code discipline (0 ok / 1 error / 2 usage), asserted in tests.
- The stdout cd-protocol is tested by an invariant test
  (`tests/test_cli.py::test_wrapper_protocol_invariant`) - a genuinely hard
  contract to keep, well guarded.
- mypy strict with zero ignores; ruff gate runs inside pytest.
- Greedy-alias parser is small, closed-set, and exhaustively parametrized.

### 1.3 Findings

Severity: C = critical, M = major, m = minor, N = nit.

| ID | Sev | Area | Finding | Evidence | Recommendation |
|----|-----|------|---------|----------|----------------|
| F1 | M | README vs code | Default data dir: README says "Default: project dir (Waypoint/)" and Files tree; `data_dir()` returns `~/.waypoint` since commit b725ecc. `wp config` prints `home: C:\Users\Leonardo\.waypoint`. INSPECTOR.md (sec 4) inherits the stale expectation. | `store.py:51-62`, `README.md:134`, commit b725ecc, observed `python -m waypoint config` | Keep `~/.waypoint` (deliberate change), sync README + INSPECTOR (Phase 5) |
| F2 | M | bookmarks.py | `_rm` lossy suffix strip: `alias.rstrip(" *")` strips ANY trailing mix of spaces/asterisks. A bookmark legitimately named `dev*` (allowed by `validate_alias`) gets deleted as `dev` when the user runs `wp rm dev*` - wrong-target deletion. Verified: `"dev*".rstrip(" *") == "dev"`. | `bookmarks.py:43-44` | Exact-suffix strip; regression test (Phase 1) |
| F3 | M | launcher.py | `wp -vs` likely fails for standard VS Code installs: `subprocess.Popen(["code", target])`; Windows resolves only `.exe` via CreateProcess, and VS Code registers `code.cmd` on PATH -> FileNotFoundError. INSPECTOR.md:200 claims dispatch is `os.startfile`/ShellExecute - stale; code is `subprocess.Popen`. | `launcher.py:28`, `INSPECTOR.md:200-201` | Resolve via `shutil.which` + `cmd /c` for .cmd shims; verify on this machine (Phase 1) |
| F4 | m | handlers | 7 `assert` statements used as type-narrowing / control flow. Stripped under `python -O`; then `None` flows into string ops -> TypeError. Never run with -O today, but wrong tool. | `bookmarks.py:41,87`, `config.py:25,48`, `launcher.py:22`, `nav.py:33,45` | Replace with explicit checks or typed payloads (Phase 2) |
| F5 | m | resolver + wrapper | `_record_history` is a hidden reserved keyword / internal command between install.ps1 and the CLI. README's "closed set" of reserved words omits it; README:117 says history.yaml holds "origins of every successful wp jump" but the wrapper now records every `cd` origin (commit 35c4b48). Also: wp jumps double-record (CLI `_record_origin` + wrapper `_record_history`); dedupe hides it. | `resolver.py:14`, `install.ps1:54`, `README.md:86,117` | Document in README; add CLI tests for `_record_history` (Phase 4) |
| F6 | m | store.py | Internal docs stale: module docstring says "two YAML data files" (manages three); `data_dir()` docstring lists a "-> project dir" fallback that no longer exists. | `store.py:1,51` | Fix docstrings (Phase 3) |
| F7 | m | store.py | `load_config` does not type-check the `home` value: a non-string (e.g. `home: 5`) passes `load_config`, then `Path(home)` raises an uncaught TypeError in `data_dir()`. | `store.py:73-86` | Validate -> StoreError (Phase 3) |
| F8 | m | commands/__init__.py | Package init re-exports all underscore-private handlers plus `pyperclip` "for test compatibility"; tests import privates across the package boundary (`from waypoint.commands import _nav`). Public-ish surface of private names. | `commands/__init__.py:8-44`, `tests/test_nav_commands.py:6` | Tests import from concrete modules; slim `__init__` (Phase 2) |
| F9 | m | nav.py | No-move detection is case-sensitive string equality: `origin == target`. On Windows, a bookmark stored with different case than `os.getcwd()` records a no-move origin into history. | `nav.py:21` | `os.path.normcase` compare (Phase 1) |
| F10 | m | install.ps1 | Interactive-command list `$interactiveCmds = @('add')` must stay hand-synced with Python-side `Prompt.ask` usage; AGENTS.md flags it, nothing enforces it. | `install.ps1:78`, `AGENTS.md` | Contract test that cross-checks the list (Phase 4) |
| F11 | m | install.ps1 | Profile path hardcoded to `$HOME\Documents\WindowsPowerShell\...` (Windows PowerShell 5.1). Terminal is Windows Terminal; pwsh 7 users get the function in a profile their shell never loads. | `install.ps1:108` | Use the running shell's `$PROFILE` (or both) (Phase 5) |
| F12 | N | store.py | `PROJECT_DIR = Path(__file__).resolve().parent.parent` breaks for non-editable installs (config.yaml would be written into site-packages). Safe today because install.ps1 always uses `pip install -e`. | `store.py:30` | Document the constraint; keep editable-only (Phase 5 note) |
| F13 | N | repo | `tmp/` not in .gitignore (leftover `wp-inspect-workspace`); `misc/*` ignore means this plan doc itself is untracked. Stale untracked root data files (`waypoint.yaml` with `test_alias` residue, `history.yaml` with real paths) are leftovers from the pre-b725ecc layout. | `.gitignore`, repo root listing | Gitignore hygiene; user-confirmed cleanup (Phase 5) |
| F14 | N | store.py | `_atomic_write` has no fsync and does not mkdir parents for the config path (save_config_home). `os.replace` semantics are fine on Windows same-volume. | `store.py:144-147` | mkdir + fsync (Phase 3) |
| F15 | N | tests | Coverage gaps: `wp store` (kind="store") and `_record_history` have NO tests; `_ls` empty state, `_undo N > available`, `wp store <alias>` alias form untested. | grep of `tests/` | Add tests (Phases 1/4) |
| F16 | N | conftest.py | `pytest_sessionstart` runs `ruff check .` via subprocess and aborts the suite (rc 2) if ruff is missing - test run coupled to a linter install. Deliberate ("pytest doubles as the check") but surprising for minimal venvs/CI. | `conftest.py:12-18` | Decouple into a separate gate script (Phase 6) |
| F17 | N | resolver | `looks_like_path` ignores bare `~`: `wp add ~` is treated as alias named "~" (path-form only triggers on `/` or `\`). Edge, documented behavior today. | `resolver.py:140-142` | Optional: treat `~` as path-form (Phase 7) |

### 1.4 Deliberate design decisions (NOT to be "fixed")

- Greedy alias parsing with a closed reserved set - documented, tested, keep.
- `temp` slot semantics (`wp default .` overwrites `temp` by design).
- `null` literal sentinel in `config.yaml`.
- Stale history entries auto-skipped at undo time rather than pruned at write.
- Everything on stdout, never stderr (PowerShell red-record behavior).
- The 3-line exit-code contract (0/1/2).

---

## Part 2 — Sequential Implementation Plan

### Global execution rules (every phase)

1. Work on `dev` only; never commit to `master` (AGENTS.md).
2. Every phase ends with the gates green:
   - `python -m pytest -q` (all pass)
   - `python -m ruff check .`
   - `python -m mypy waypoint`
   - If `misc/INSPECTOR.md` conformance protocol was run in the phase, `DISSONANCES.md` must be clean or the dissonances must be exactly the ones the phase intended.
3. User-facing output stays ASCII-only (AGENTS.md "Fuckups" rule).
4. No new dependencies. No new files outside `waypoint/`, `tests/`, `misc/`,
   `install.ps1`, and the root docs.
5. Each phase's tests must be added in the same phase as the code change.
6. Never delete untracked user data without confirmation (see Phase 5).

---

### Phase 1 — Behavior bug fixes (semantics preserved except the listed bugs)

**Objective:** eliminate the three wrong-behavior findings before any structural
work: wrong-target bookmark deletion (F2), broken VS Code launch (F3), spurious
history entries from path-case mismatch (F9).

**Changes:**

1. `waypoint/commands/bookmarks.py` (`_rm`):
   - Replace `alias.rstrip(" *")` with an exact-suffix rule: strip only one
     trailing `" *"` (the `wp ls` default-marker label), i.e.
     `alias.removesuffix(" *")` when the exact suffix is present. A bookmark
     named `dev*` or `dev**` must never be rewritten to `dev`.
   - Keep the copy-paste-from-`ls` convenience intact (that is its purpose).
2. `waypoint/commands/nav.py` (`_record_origin`):
   - Compare `origin` and `target` via `os.path.normcase(...)` so Windows path
     case differences do not record a no-move origin.
3. `waypoint/commands/launcher.py` (`_open`):
   - Resolve the executable with `shutil.which`; if the resolved path ends in
     `.cmd`/`.bat`, launch via `Popen(["cmd", "/c", resolved, target])`;
     otherwise plain `Popen([resolved, target])`. `explorer.exe` is unaffected.
   - Keep the FileNotFoundError -> "not found on PATH" error path.
   - **Verify on this machine:** run `wp -vs` once with a default bookmark
     pointing at a scratch dir inside `tmp/`; confirm exit 0 and the
     "Opening <path> in VS Code" line, and that VS Code actually opens.
4. Tests:
   - `_rm` regression: seed bookmarks `dev` and `dev*`; `wp rm dev*` must
     remove `dev*` and leave `dev`; `wp rm "dev *"` (the ls label form) must
     still remove the default `dev`.
   - `_record_origin` case test: bookmark stored with a different case than
     `os.getcwd()` -> no history entry.
   - Add missing `wp store` coverage (see F15): `wp store` (print paths),
     `wp store <alias>` (uses bookmark path), `wp store <path>` (auto-create).
   - Add `_ls` empty-state test (hint text, exit 0).

**Definition of Done:** all gates green; the three behavior fixes have a
regression test each; `wp -vs` verified manually on this machine.

---

### Phase 2 — Kill `assert`-narrowing; type the `Command` payload

**Objective:** remove the 7 `assert`-as-control-flow sites (F4) by giving every
command kind a typed payload, and slim the `commands/__init__.py` surface (F8).

**Changes:**

1. `waypoint/resolver.py`:
   - Replace the single `Command(kind, args: list[str | None])` with per-kind
     dataclasses: `Nav(alias: str | None)`, `Add(alias: str | None, path: str |
     None)`, `Rm(alias)`, `Ls`, `Default(arg)`, `Set(arg: str | None)`,
     `ConfigHome(target: str | None)`, `Store(arg: str | None)`, `Help`,
     `History(full: bool)`, `Undo(steps: int | None)`, `Open(kind)` (explorer /
     code), `RecordHistory(origin: str)`.
   - Keep a `Command` type alias (the union) so `cli.dispatch` and existing
     callers keep working; `parse_args` returns the union.
   - The parametrized parse matrix in `tests/test_resolver.py` locks the
     surface - update the expected objects to the new classes; the table stays
     the same shape so this is mechanical.
2. Handlers (`nav.py`, `history.py`, `bookmarks.py`, `config.py`, `launcher.py`):
   - Drop every `assert x is not None`; mypy now proves the fields. Where a
     field is genuinely optional by design (e.g. `Add.alias`, `Set.arg`), the
     None branch is already the prompting/fallback path - no error handling
     changes.
3. `cli.py` `dispatch`: switch the `cmd.kind` if-chain to isinstance dispatch
   (or keep `kind` as a property on each class - pick one, do not keep both).
4. `waypoint/commands/__init__.py`:
   - Remove the private re-exports and the unused `import pyperclip`.
   - Update tests to import from concrete modules
     (`waypoint.commands.nav`, `waypoint.commands.bookmarks`, ...) instead of
     the package init. Add a lint-level test that asserts
     `waypoint.commands` exposes no underscore-prefixed names.

**Definition of Done:** all gates green; `grep -n "assert" waypoint/` returns
nothing outside tests; no test imports `_`-prefixed names from
`waypoint.commands`.

---

### Phase 3 — Store-layer hardening

**Objective:** make the data layer robust where the audit found holes (F6, F7,
F14), with zero behavior change to the CLI surface.

**Changes** (`waypoint/store.py` + `tests/test_store.py`):

1. `load_config`: validate `home` is `None` or a string; raise `StoreError`
   otherwise (covers `home: 5` -> clear error instead of TypeError).
2. `_atomic_write`: `path.parent.mkdir(parents=True, exist_ok=True)` before
   writing; `flush()` + `os.fsync` the tmp file before `os.replace`.
3. Docstrings: module header says "three YAML data files"; `data_dir()`
   docstring states the real fallback order: `WP_HOME -> config home ->
   ~/.waypoint` (drop the stale "-> project dir").
4. Tests: non-string `home` raises `StoreError`; atomic write creates missing
   parent dirs; existing round-trip tests must stay untouched and green.

**Definition of Done:** all gates green; store tests cover the two new error
paths; no CLI test changed in this phase.

---

### Phase 4 — Wrapper contract: test, document, de-risk (F5, F10)

**Objective:** make the install.ps1 <-> CLI coupling explicit and drift-proof.
No protocol change - the `_record_history` command and `WP_FORCE_COLOR` env
stay (they work); they become tested and documented.

**Changes:**

1. Tests (`tests/test_wrapper_contract.py`):
   - `_record_history` CLI tests: records a valid dir; ignores a non-dir;
     dedupes consecutive identical origins; `wp _record_history` with no arg is
     a usage error (exit 2); the command never prints a bare-path line (cd
     protocol safe).
   - Parse `install.ps1` text in a test and assert its `$interactiveCmds` list
     equals the set of command kinds whose handlers reach `Prompt.ask`
     (today: exactly `add`). Drift in either direction fails the suite.
2. `waypoint/resolver.py`: keep `_record_history` in RESERVED (it must stay
   un-usable as a bookmark name); no code change.
3. `README.md` (docs only, full sync is Phase 5 - do the history-semantics
   lines here so Phase 5 is pure consistency): document `_record_history` as an
   internal wrapper command and correct line 117's claim that history.yaml
   holds only wp-jump origins (it holds every cd origin; wp jumps and plain
   `cd` both feed it, deduped).
4. Note in the phase log the double-record path (CLI `_record_origin` + wrapper
   `_record_history` for the same wp jump) as accepted, dedupe-protected
   behavior - do not "fix" it.

**Definition of Done:** all gates green; `test_wrapper_contract.py` passes;
README history semantics corrected.

---

### Phase 5 — Spec sync (README is the spec) & repo hygiene

**Objective:** README.md and misc/INSPECTOR.md describe the actual system
(F1, F11, F12, F13). This phase must come after the behavior phases so the docs
describe the post-refactor truth.

**Changes:**

1. `README.md`:
   - Data section: default storage dir is `~/.waypoint` (not project dir);
     "three YAML files" (config.yaml lives in the project dir, waypoint.yaml +
     history.yaml live in the data dir).
   - Reserved keywords: add `_record_history` (internal) to the list; adjust
     the "closed set" claim to "closed user-facing set plus one internal
     command".
   - Files tree: match reality (add `misc/REFACTORING_PLAN.md`, the
     `tmp/`-scratch note, and the new test files).
   - Notes: editable-install-only constraint for `PROJECT_DIR` (F12).
2. `misc/INSPECTOR.md`:
   - Fix the os.startfile claim in the "Open locations" section (dispatch is
     `subprocess.Popen`; the PATH-shim note is still valid - a shim is never
     invoked, which is why `code.cmd` needs the Phase 1 resolution fix).
   - Fix the Configure-section expectation: default location is `~/.waypoint`.
3. `install.ps1` (F11): target the running shell's profile: use
   `$PROFILE.CurrentUserAllHosts` or detect pwsh vs WindowsPowerShell and write
   to the matching profile; keep the marker-block replace logic.
4. Hygiene (F13):
   - `.gitignore`: add `tmp/`; decide the `misc/` exception - recommend
     `!misc/INSPECTOR.md` + `!misc/REFACTORING_PLAN.md` so both protocol and
     plan are tracked (ask the user; this is a repo-policy choice).
   - Stale root data files (`waypoint.yaml` with `test_alias` residue,
     `history.yaml`, `config.yaml`): **user confirmation required before
     deletion** (they are untracked user data). Recommend: archive under
     `tmp/` first, then delete after one week of normal use.

**Definition of Done:** README and INSPECTOR contain no statement contradicted
by the code; the INSPECTOR Configure + Open sections match observed behavior;
gitignore hygiene committed; user decision on data files recorded.

---

### Phase 6 — Quality-gate decoupling (F16)

**Objective:** `pytest` runs tests; lint runs lint.

**Changes:**

1. `tests/conftest.py`: remove `pytest_sessionstart` ruff gate.
2. Add `scripts/check.ps1` (or `check.py`) that runs, in order: ruff, mypy,
   pytest. README install/develop section points at it.
3. Optional (ask the user): add a minimal GitHub Actions workflow running
   `scripts/check` on Python 3.10-3.13, Windows + Ubuntu. If the project
   prefers no CI, skip.

**Definition of Done:** `pytest -q` passes in a venv without ruff installed;
`scripts/check` passes everywhere; README documents the check entry point.

---

### Phase 7 — Stretch backlog (optional; only if the user opts in)

Each item is independent; execute in listed order if selected:

1. `looks_like_path`: treat bare `~` as path-form so `wp add ~` and
   `wp set ~` behave like paths (F17).
2. `Bookmarks` paths as `Path` objects internally (normalize at the store
   boundary) - larger blast radius, only if the string-path ergonomics ever
   hurt.
3. `wp help` parity test: assert every reserved keyword appears in help output
   (guards the "closed set" doc claim mechanically).
4. `prompt_name` loop simplification: hoist the explicit-alias error path out
   of the while loop.

---

## Part 3 — Execution checklist (per phase)

1. `git checkout dev && git pull` (confirm clean tree).
2. Read this phase's section again; implement changes + tests together.
3. Run gates: `python -m pytest -q`, `python -m ruff check .`,
   `python -m mypy waypoint`.
4. If the phase touches the wrapper (4) or launcher (1), run the manual
   verification steps listed there.
5. Commit on `dev` with a message naming the phase
   (`refactor(phase N): <summary>`).
6. Tick the phase off in this file's phase log (below).

## Phase log

| Phase | Status | Date | Notes |
|-------|--------|------|-------|
| 1 Behavior bug fixes | complete | 2026-08-04 | Fixed F2 (_rm removesuffix), F3 (launcher shutil.which), F9 (normcase history), added regression tests |
| 2 Typed Command payloads | complete | 2026-08-04 | Replaced Command(kind, args) with dataclass union, eliminated 7 assert statements, slimmed commands package init |
| 3 Store hardening | complete | 2026-08-04 | Added home type check, fsync atomic write, parent mkdir, and updated store docstrings |
| 4 Wrapper contract | complete | 2026-08-04 | Added test_wrapper_contract.py (_record_history + $interactiveCmds sync), updated README history docs |
| 5 Spec sync & hygiene | complete | 2026-08-04 | Synced README + INSPECTOR to post-refactor truth, updated install.ps1 profile resolution, gitignore hygiene |
| 6 Gate decoupling | pending | | |
| 7 Stretch backlog | pending | optional |

## Part 4 — Open questions register (decisions required)

Every phase-gating decision below is genuinely contested; the plan runs with
the marked default until the owner decides. Answering a question updates the
default in the affected phase(s). Do not silently re-decide an answered row.

| ID | Question | Options | Plan default | Gates | Status |
|----|----------|---------|--------------|-------|--------|
| Q1 | Default data dir: is `~/.waypoint` (code since b725ecc) intended, or should code revert to README's project dir? | a) docs -> code b) code -> README c) platformdirs-style location | a | Phase 5 (F1) | open |
| Q2 | History semantics: should every `cd` feed history.yaml (current) or only wp jumps (README claim)? | a) document current b) wrapper stops persisting cds | a | Phase 4 (F5) | open |
| Q3 | Scope: may the refactor change behavior (Phase 1 fixes) or must it be behavior-neutral? | a) fixes in-plan b) fixes as separate change set | a | Phase 1 | open |
| Q4 | Command typing: per-kind dataclasses vs minimal explicit None-checks | a) dataclass union b) keep kind+args | a | Phase 2 (F4) | open |
| Q5 | pytest-as-gate: keep ruff inside pytest sessionstart (deliberate) or decouple? | a) decouple b) keep | a | Phase 6 (F16) | open |
| Q6 | `wp rm "dev *"` convenience: keep (exact suffix), drop, or error-with-hint? | a) keep b) drop c) hint | a | Phase 1 (F2) | open |
| Q7 | `misc/*` gitignore: track plan + INSPECTOR or keep misc as scratch? | a) track both b) keep ignored | a | Phase 5 (F13) | open |
| Q8 | INSPECTOR conformance re-runs: after Phases 1 + 5, after every phase, or once at the end? | a) after 1 + 5 b) every phase c) once at end | a | All | open |
| Q9 | CI: add a minimal GitHub Actions check workflow? | a) no CI b) yes | a | Phase 6 | open |

### How to answer

State the ID and the chosen option (e.g. "Q4 -> b"). The plan owner updates the
row (Status: decided, note the option) and amends the affected phase's Changes
section before executing it. Questions that stay open at a phase boundary are
executed with the plan default, and the phase log records that the default was
used.

