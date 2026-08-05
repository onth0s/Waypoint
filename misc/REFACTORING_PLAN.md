# REFACTORING_PLAN.md — Waypoint Codebase Audit & Sequential Refactor Plan

Run date: 2026-08-05 | Branch: `dev` | Baseline: 189 tests passing, ruff clean, mypy strict clean.

This document is the product of a full audit of the Waypoint codebase and the
refactoring plan that follows from it. It supersedes the previous plan (executed
in phases 1-6, see git log `d1480f6..`). **The plan MUST be executed
sequentially: finish every phase in order, and never start phase N+1 until phase
N meets its Definition of Done.** Phases are ordered so that behavior fixes land
first (cheapest while the code is fresh), structural cleanup second, consistency
and docs third, and test-only hardening last.

---

## Part 1 — Audit

### 1.1 Scope & ground truth

- Code: `waypoint/` (15 source files, 1,077 lines), `install.ps1`, `pyproject.toml`, `scripts/check.ps1`.
- Tests: `tests/` (9 files, 1,447 lines, 189 tests).
- Spec: `README.md` is the sole ground truth (per `misc/INSPECTOR.md`).
- Verification state at audit time:
  - `python -m pytest -q` -> 189 passed
  - `python -m ruff check .` -> All checks passed
  - `python -m mypy waypoint` -> Success: no issues found in 15 source files

### 1.2 Architecture (as-built)

```
__main__.py -> cli.main() -> parse_args (resolver) -> dispatch (cli) -> handlers (commands/)
                                                     |-> store (YAML I/O, atomic writes, data-dir resolution)
                                                     |-> output / prompts / clipboard (services)
                                     install.ps1 (PowerShell wrapper) <-> CLI via:
                                       stdout protocol (single existing-path line = cd),
                                       WP_FORCE_COLOR env, `_record_history` hidden command
```

Status of the previous audit's findings (F-series, plan `d1480f6`): all 17
resolved or deliberately kept. Verified in this audit: `_rm` exact-suffix strip
(`removesuffix(" *")`), launcher `.cmd/.bat` shim resolution via
`shutil.which` + `cmd /c`, no `assert`-as-control-flow remaining, store
`home` type-checking, fsync'd atomic writes with parent mkdir, normcase no-move
detection in `_record_origin`, slim `commands/__init__.py`, `$interactiveCmds`
contract test, `$PROFILE`-based installer path, decoupled `scripts/check.ps1`
gate, empty `commands/__init__.py`.

Strengths (do not refactor these away):

- Clean layering: constants -> services -> store -> resolver -> handlers -> cli.
- Atomic writes (`tmp` + `os.replace`) for all YAML files.
- Exit-code discipline (0 ok / 1 error / 2 usage), asserted in tests.
- The stdout cd-protocol is tested by an invariant test
  (`tests/test_cli.py::test_wrapper_protocol_invariant`) — a genuinely hard
  contract to keep, well guarded.
- mypy strict with zero ignores.
- Greedy-alias parser is small, closed-set, and exhaustively parametrized
  (`tests/test_resolver.py`, 44 parse cases + 28 usage-error cases).
- Duplicated `_set`/`_default` logic is the only real structural smell (G5).

### 1.3 Findings

Severity: C = critical, M = major, m = minor, N = nit.

| ID | Sev | Area | Finding | Evidence | Recommendation |
|----|-----|------|---------|----------|----------------|
| G1 | M | commands/config.py | `_store` truncates `~` paths: the branch `arg == "~" or arg.startswith("~/") or arg.startswith("~\\")` expands only `"~"`, dropping the subpath. `wp store ~/dev/foo` sets the store home to `C:\Users\<user>` instead of `C:\Users\<user>\dev\foo` — silent wrong-target write. Reproduced: `expanduser("~")` vs `expanduser("~/dev/foo")`. | config.py:51-52 | Collapse to `elif arg.startswith("~"): target_path = os.path.expanduser(arg)`; regression tests (Phase 1) |
| G2 | m | commands/history.py | `_record_history_entry` dedupes with case-sensitive `!=`, while `_record_origin` (nav.py) uses `os.path.normcase`. On Windows the wrapper's `cd` path (`install.ps1` -> `_record_history`) can record duplicate origins that differ only in case; the CLI nav path does not. | history.py:23, nav.py:24 | normcase compare in `_record_history_entry` (Phase 1) |
| G3 | m | store.py | `_atomic_write` uses a fixed tmp name (`path.name + ".tmp"`). Two concurrent writers to the same file (two `wp add` in parallel shells, or a wrapper `_record_history` racing an `undo`) can clobber each other's tmp file: the loser's open handle is orphaned by the winner's `os.replace`, then its own `os.replace` raises FileNotFoundError -> traceback. | store.py:151 | Unique tmp per write via `tempfile.mkstemp(dir=path.parent, ...)` + `os.replace` (Phase 1) |
| G4 | m | commands/launcher.py | `_open` catches only `FileNotFoundError` from `subprocess.Popen`; any other `OSError` (access denied, etc.) escapes as a raw traceback instead of a clean error line. | launcher.py:36 | Catch `OSError` (Phase 1) |
| G5 | m | commands/bookmarks.py | `_default` and `_set` are ~95% duplicate logic: for every non-None arg the two bodies are byte-identical (`"."` -> temp/cwd; bookmark alias -> default; path -> temp slot; else `BookmarkNotFoundError`). Only `_set`'s `arg is None` clipboard branch differs. Duplicated branch trees drift independently. | bookmarks.py:88-117 | Merge into one `_set_default(arg, console)`; keep thin wrappers (Phase 3) |
| G6 | m | commands/history.py | `_history` displays stale (deleted-dir) entries, but `_undo` skips them. When a dead entry sits inside the 5-entry window, the displayed index `N` is NOT the `wp undo N` target — INSPECTOR.md sec 4 asserts "N stays a true undo index" (line 133). | history.py:53-61 vs 33-41 | Filter live entries in `_history` display; footer counts live entries only (Phase 2) |
| G7 | m | resolver + bookmarks/config | Bare `~` is inconsistent across sibling commands: `wp store ~` special-cases to home; `wp add ~` parses as an alias literally named `"~"`; `wp set ~` / `wp default ~` raise `BookmarkNotFoundError`. One command family, three behaviors. (Subpath `~/x` forms already work in add/set/default via `expanduser` + `looks_like_path`.) | config.py:51, resolver.py:237-239, bookmarks.py:99,116 | Treat bare `~` as path-form in add/set/default (`looks_like_path` gains `arg == "~"`); tests + README (Phase 4) |
| G8 | N | README vs code | `wp store <arg>` auto-creates the target directory (commit 4fab397), and a non-bookmark bare arg with no slash (e.g. `wp store foo`) silently creates `./foo` in the cwd. README:54 says only "store bookmarks at <alias> target or <path>". Undocumented side effect. | config.py:57-61 | Document in README (Phase 4) |
| G9 | N | store.py | `data_dir()` re-reads `config.yaml` from disk on every call; each command performs >= 2 disk loads (config + bookmarks + history). Negligible for a CLI; no caching warranted. | store.py:53-64 | Keep; note only |
| G10 | N | commands/config.py | `"null"` sentinel is special-cased in two places (`_config`, `_store`) with duplicated case-insensitive strip logic; a real directory literally named `null` can never be selected as home. Deliberate, documented design. | config.py:25,53 | Keep; hoist to a shared helper only if a third use appears |
| G11 | N | commands/bookmarks.py | `_ls` renders paths in a rich `Table`, which truncates long paths at terminal width. history.py deliberately avoids tables for exactly this reason ("full paths must survive the 80-col pipe"). `ls` display can hide a path tail. | bookmarks.py:67-71 | Accept (cosmetic) or switch to prefixed lines like history; decide, then keep |
| G12 | N | tests | Coverage gaps (no behavior change intended): `wp store ~`/`~/x` forms (G1 is unguarded), `_open` missing exe / missing default / `.cmd` shim branch, `_undo` with count > available, `wp store` bare-arg dir creation, concurrent `_atomic_write`, stale-entry window (G6). | grep of `tests/` | Add tests (Phases 1/2/5) |
| G13 | N | prompts.py | `prompt_name` re-prompts on an invalid *prompted* name but raises `UsageError` (exit 2) on an invalid *explicit* alias — asymmetric UX, deliberate and tested (test_add_reserved_alias_is_usage_error). | prompts.py:34-57 | Keep; documented here |

### 1.4 Deliberate design decisions (NOT to be "fixed")

- Greedy alias parsing with a closed reserved set (incl. the hidden
  `_record_history` keyword; documented in README:86).
- `temp` slot semantics (`wp default .` overwrites `temp` by design).
- `null` literal sentinel in `config.yaml`; `home: null` reset contract.
- Stale history entries auto-skipped at undo time rather than pruned at write.
- Everything on stdout, never stderr (PowerShell red-record behavior).
- The 3-line exit-code contract (0/1/2).
- `wp add` requires an existing target directory; only `wp store` auto-creates.
- Editable-only install: `PROJECT_DIR` derives from `__file__` (README:212).
- Typed command dataclasses + isinstance dispatch in `cli.dispatch` — tested,
  exhaustive; no argparse/typer migration.

---

## Part 2 — Refactoring Plan (execute in order)

Every phase: implement, run `.\scripts\check.ps1`, commit on `dev` (never
`master`), then update the tracking table in Part 3.

### Phase 1 — Correctness fixes (bugs first)

**Goal:** land the four behavior bugs while the code is fresh; each with a
regression test.

1. **G1** — `commands/config.py` `_store`: replace the tilde elif-chain with
   `elif arg.startswith("~"): target_path = os.path.expanduser(arg)`. Covers
   `~`, `~/x`, `~\x` uniformly; `os.makedirs` behavior unchanged.
   Tests: `wp store ~/sub` (with `WP_HOME` unset and monkeypatched
   `PROJECT_DIR`) -> `load_config()["home"] == normpath(expanduser("~/sub"))`;
   `wp store ~` -> home dir; `wp store ~\sub` -> backslash form.
2. **G2** — `commands/history.py` `_record_history_entry`: compare with
   `os.path.normcase` (mirror nav.py:21-26). Test: record `C:\Foo`, then
   `c:\foo` (dirs must exist case-insensitively on Windows; use tmp_path) ->
   history has one entry. Wrapper contract test still passes.
3. **G3** — `store.py` `_atomic_write`: unique tmp file per write via
   `tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")`,
   write + flush + fsync through `os.fdopen`, then `os.replace(tmp_name, path)`.
   Same-volume replace keeps atomicity. Test: a pre-existing stale
   `waypoint.yaml.<rand>.tmp` residue does not break the next write; two
   sequential writes to the same path both succeed.
4. **G4** — `commands/launcher.py` `_open`: broaden `except FileNotFoundError`
   to `except OSError` (message unchanged). Test: monkeypatch
   `subprocess.Popen` to raise `PermissionError` -> exit `EXIT_ERROR`, no
   traceback, error line on stdout.

**Definition of Done:** `.\scripts\check.ps1` green; G1-G4 each covered by a
new test that fails on the pre-fix code.

### Phase 2 — History display/undo index alignment & `wp h N` alias

**Goal:** make the printed history index a true `wp undo` index (INSPECTOR.md
sec 4 contract) even when stale entries exist, and allow `wp h N` / `wp history N`
as a convenient shorthand alias for `wp undo N`.

1. `resolver.py`: update `_parse_history` so if `rest` is a single positive integer $N$,
   it returns `UndoCmd(steps=int(N))`.
2. `commands/history.py` `_history`: filter `entries` to live dirs
   (`os.path.isdir`) before windowing, reversing, and indexing. `shown` =
   live tail of `HISTORY_PREVIEW` (or all live when `full`). Footer `(K more…)`
   counts *live* entries outside the window — `--all` must show exactly the
   listed set. If no live entries remain, keep the existing "No navigation
   history yet" hint (exit 0). Empty-file case unchanged.
3. Test: seed history `[live_a, dead, live_b, dead, live_c]` (dead = dirs
   removed after recording) -> `wp history` lists 3 rows with indexes 1..3
   matching `wp undo 1|2|3` (and `wp h 1|2|3`) targets; footer math holds when live count > 5.
3. `_undo` itself is unchanged (already correct).

**Definition of Done:** index-alignment test passes; check.ps1 green; no change
to `_undo`, `_record_origin`, or the history file format.

### Phase 3 — De-duplicate `_set` / `_default`

**Goal:** one implementation for the shared "set default" behavior; zero
user-visible change.

1. `commands/bookmarks.py`: add `_set_default(arg: str | None, console) -> int`
   containing the merged body: `None` -> `_set_temp_slot(clipboard or cwd)`
   (reachable only from `set`); `"."` -> temp slot = cwd; bookmark alias ->
   set `b.default`; path-looking (incl. bare `~` after Phase 4) -> temp slot =
   `abspath(expanduser(arg))`; else `raise store.BookmarkNotFoundError(arg)`.
2. `_default(cmd)` -> `return _set_default(cmd.arg, console)`;
   `_set(cmd)` -> `return _set_default(cmd.arg, console)`. Keep both exported
   (cli.dispatch and `__all__` unchanged). Keep `_set_temp_slot`.
3. No resolver or dispatch changes.

**Definition of Done:** all existing set/default tests pass unmodified; a new
test asserts `_set` and `_default` produce identical state for the same
argument; check.ps1 green.

### Phase 4 — Bare-`~` consistency + README sync

**Goal:** one `~` behavior across `add`/`set`/`default`/`store`; document the
`wp store` auto-create side effect.

1. `resolver.py`: `looks_like_path(arg)` gains `arg == "~"` (single source:
   `return arg == "~" or any(sep in arg for sep in ("\\", "/"))`). Effect:
   `wp add ~` -> path-form (prompts for name, bookmarks home); `wp set ~` /
   `wp default ~` -> temp slot = home; `wp store ~` unchanged. An alias
   literally named `~` becomes uncreatable via CLI args (still creatable via
   the interactive prompt — accepted; the reserved set does not grow).
2. README:
   - `wp store <alias|path>` section: state that the target directory is
     auto-created when missing, and that a bare non-bookmark argument creates
     it relative to the cwd (G8).
   - `wp add` / `wp set` / `wp default` lines: note `~` and `~/…` forms resolve
     to the home directory / a subpath of it.
   - Greedy-alias note: nothing changes in the reserved set.
3. `_help` text: add the `~` forms to the `wp default` / `wp set` lines.

**Definition of Done:** `wp add ~`, `wp set ~`, `wp default ~` covered by
tests; README + `_help` reflect G8 and the `~` behavior; check.ps1 green.

### Phase 5 — Coverage hardening (tests only, no behavior change)

**Goal:** close the G12 gaps; any test that exposes a real defect gets fixed
in this phase and noted.

1. `_open`: missing default bookmark -> exit 1 + error; `shutil.which` ->
   None -> "not found on PATH"; `.cmd` shim branch -> Popen called with
   `["cmd", "/c", resolved, target]` (mock `shutil.which` and `Popen`).
2. `_undo 3` with fewer than 3 live entries -> exit 1, "No navigation history
   to undo.", no protocol hit.
3. `wp store foo` (no slash, not a bookmark) -> creates `./foo`, config home
   set (locks in G8 behavior).
4. `_atomic_write` residue test if not already in Phase 1.
5. `_ls` default-marker + empty-state assertions (partially present; complete).

**Definition of Done:** coverage additions pass; check.ps1 green; zero source
changes except documented defect fixes.

### Phase 6 — Final verification & docs (last)

**Goal:** close the loop; leave the repo green and the spec accurate.

1. Full `.\scripts\check.ps1` run on a clean tree; record results.
2. Re-read `README.md` and `misc/INSPECTOR.md` against the shipped behavior:
   - Phase 2 makes INSPECTOR sec 4's "true undo index" claim accurate — verify,
     do not edit unless a mismatch appears.
   - README "Files" tree must match reality (nothing is expected to move).
3. Update Part 3 tracking table with commit hashes and phase status.
4. Commit any docs drift on `dev`.

**Definition of Done:** check.ps1 green; INSPECTOR/README verified consistent;
tracking table complete; no open findings from Part 1 (all G-IDs resolved or
explicitly marked `keep`).

---

## Part 3 — Phase tracking

| Phase | Content | Status | Commit |
|-------|---------|--------|--------|
| 1 | Correctness fixes (G1-G4) | pending | — |
| 2 | History/undo index alignment (G6) | pending | — |
| 3 | `_set`/`_default` merge (G5) | pending | — |
| 4 | Bare-`~` consistency + README (G7, G8) | pending | — |
| 5 | Coverage hardening (G12) | pending | — |
| 6 | Final verification & docs | pending | — |

Findings disposition: G1-G4 fix in Phase 1; G6 in Phase 2; G5 in Phase 3;
G7-G8 in Phase 4; G12 in Phase 5; G9-G11, G13 keep (documented rationale in
1.3/1.4).
