# INSPECTOR.md — Black-Box CLI Conformance Protocol

Run this protocol to verify that every command on the Waypoint CLI behaves the way
`README.md` says it does, and to record any dissonance.

## 1. Ground truth & scope

- **Sole ground truth:** `README.md`. Nothing else in the repo is authoritative.
- **Scope:** user-visible usage — command semantics, stdout output contract, exit
  codes, and file side effects (the YAML data files).
- **Forbidden reads (black-box rule):** the testing agent MUST NOT open any codebase
  source or config:
  - `waypoint/*.py`, `install.ps1`, `pyproject.toml`, `tests/`
  - the repo copies of `config.yaml` and `waypoint.yaml`

  The agent's only windows into the program are:
  1. captured `stdout` / `stderr` / exit code of each invocation, and
  2. the YAML state files that the program writes **inside the isolated test
     workspace** (see §2).
- If observed behavior contradicts README in any way not covered by (1) and (2),
  that contradiction is itself a dissonance.

## 2. Isolation harness

Every run creates a fresh temp workspace and never touches real bookmarks.

```
T/            temp workspace (use C:\Users\<user>\AppData\Local\Temp\opencode\wp-inspect-<ts>)
  home/       ← WP_HOME destination; only YAML files written here may be read
  cwd/        scratch cwd; commands are run with this as the working directory
    src/      a known subdir used for path-dependent probes
  config/     INERT: the tool reads config.yaml from the project dir, not from
              here. Kept only for historical layout; see §4 Configure for the
              real precedence-probe procedure.
  out.txt     captured stdout
  err.txt     captured stderr
  transcript.txt   full probe log (command + exit code + outputs)
```

Rules:

- Every probe sets `WP_HOME=T\home` (unless a probe is specifically testing the
  resolution order without it — then it is unset/empty).
- Seed bookmarks only through the CLI itself (black box), never by hand-writing YAML.
- cwd-dependent probes (`wp add` bare, `wp set`, `wp default .`) run with cwd = `T\cwd\src`.
- At the end, delete `T`.

### Harness rules (known failure modes — read before writing any probe script)

- **Never name a harness parameter after a PowerShell automatic variable.** Real
  breakages observed on 2026-08-04:
  - `$Home` → `$HOME` is read-only; the script aborts at binding time
    (`Cannot overwrite variable Home because it is read-only or constant`).
  - `$Args`/`$args` → splatting `@Args` silently splats the *automatic* variable
    (empty), so `wp add dev <path>` actually runs `wp` with NO args and navigates
    to the default instead of adding. Silent wrong observations are the worst class
    of failure — probes appear to "pass" while testing nothing.
  - Use `$WpArgs` / `$WpHome` instead. Same for `$PROFILE`, `$input`, `$PID`.
- **Canonical probe template** (L1, every probe):

  ```powershell
  $env:WP_HOME = $WpHome            # or Remove-Item Env:WP_HOME / set "" per probe
  Push-Location $ProbeCwd
  & python -m waypoint @WpArgs 1>out.txt 2>err.txt
  $code = $LASTEXITCODE             # read IMMEDIATELY after the child exits
  Pop-Location
  ```

  Always redirect `1>`/`2>` to files and read `$LASTEXITCODE` right after the
  invocation — never let another command run between the child and the capture.
- **Stateful probes never go through the `wp` wrapper.** The wrapper captures core
  stdout via `@()` and is L2-only; running `wp add` through it would test the
  wrapper, not the core, and would buffer interactive prompts.
- **Clipboard hygiene:** probes that depend on clipboard state must set or clear the
  clipboard explicitly (`Set-Clipboard ""`) before each run — a stale Explorer path
  silently changes `wp add`/`wp set` results.
- **Sanity-check the harness before the matrix:** run one warm-up probe (e.g.
  `wp ls` on a fresh `T\home`). If its output is not the bookmark table, the
  argument binding is broken (see the `$Args` trap above) — fix the harness before
  recording any observation.

## 3. Invocation layers

Both layers are exercised per the protocol owner's decision.

- **L1 — raw core (authoritative for stdout / exit / state contracts):**
  `python -m waypoint <args>` with `WP_HOME=T\home`, cwd = probe cwd.
  Capture with:

  ```powershell
  & python -m waypoint @WpArgs 1>out.txt 2>err.txt
  $code = $LASTEXITCODE
  ```

  A parameter named `$Args` silently swallows the splat (see §2 Harness rules);
  `$WpArgs` is the safe name.

- **L2 — wrapper (`wp` function):** a fresh `pwsh` that loads the `wp` function from
  `$PROFILE`, runs `wp <args>`, and asserts:
  - navigation commands changed `$PWD` to the resolved absolute path (the `cd`),
  - interactive output is colorized (ANSI codes present) because the wrapper forces
    color — verify with `wp ls` and inspect the captured output for escape sequences.

  README's cd contract (line 157): *a bare existing path on stdout is the one thing
  that triggers a `cd`.* L1 proves the bare path line is emitted; L2 proves the
  wrapper turns it into a `Set-Location`.

  **Same-directory false negative:** a cd assertion only "moves" if the target
  differs from the starting `$PWD`. `wp set` and `wp default .` set
  default = temp = current cwd, and `T\cwd\src` is the common probe cwd — running
  the nav probe right after one of those yields `moved=False` even though the cd
  succeeded. Start cd assertions from a dir that differs from the target (e.g.
  `T\cwd`, not `T\cwd\src`), or compare the after-`$PWD` against the *resolved
  target path* rather than `moved != before`.

## 4. Full command matrix

Run **every** row. L1 on all rows; L2 on the rows marked `[L2]`.

### Navigation

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp` (no args) | go to default bookmark (18, 95) | exit 0; stdout = exactly one line = resolved absolute path of default |
| `wp <alias>` | go to bookmark named alias (20) | exit 0; stdout = resolved absolute path of alias |
| `wp wp` | self-referential → project dir (95, 156) | exit 0; stdout = project dir path |
| `wp <unknown-alias>` | only reserved words run subcommands (68-71) | non-zero exit; **no** bare existing path on stdout (must never cd) |
| `wp <alias>` where alias exists | — | `[L2]`: `$PWD` == resolved path |
| `wp <alias>` then `wp undo` | record origin, walk back (19-29) | first jump seeds `history.yaml` (under `T\home`) with the pre-jump cwd; `wp undo` exits 0 and stdout = exactly that cwd; history entry removed |
| `wp undo` with empty history | — | non-zero exit; **no** bare existing path on stdout; hint text |
| `wp undo 2` | go back N steps (20) | after two recorded jumps, exits 0, stdout = origin of the jump before last; both entries popped |
| `wp undo 0` / `wp undo x` / `wp undo 1 2` | usage (20) | exit 2 with a usage message |
| `wp history` | show newest 5, newest first (22-23, 29-31) | exit 0; indexed lines `N  <path>`, newest first, at most 5 rows; `N` stays a true undo index; a `(K more; run wp h --all)` footer when deeper; **no single** bare existing-path line (§5.1) — even a one-entry history prints a prefixed line |
| `wp history --all` (+ `--full`/`full`/`all`/`f`/`a`) | full stack (23, 31-33) | exit 0; every entry printed, no footer |
| `wp history` with 6+ entries | window + footer (22, 29) | exactly 5 rows plus the `K more` footer |
| `wp h` | alias for history (20) | identical to `wp history` |
| `wp history` with empty history | — | exit 0; hint text, no bare path line |
| `wp history <other>` / extra args | usage (84) | exit 2 with a usage message |
| `wp set` / `wp default` / `wp add` | state-only, never recorded (28) | `history.yaml` unchanged after each |

### Manage bookmarks

Seed state via the CLI before each probe; re-read the YAML under `T\home` after.

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp add` (stdin-piped name) | bookmark current dir, prompts for name (28) | exit 0; bookmark with piped name == `T\cwd\src` |
| `wp add` (clipboard = valid path) | paste from Explorer (117) | bookmark name = prompt, path = clipboard path |
| `wp add` (clipboard = invalid string) | — | documented behavior for non-path clipboard |
| `wp add` (clipboard empty) | fallback to cwd | bookmark == `T\cwd\src` |
| `wp add <alias>` | bookmark current dir as alias (29) | alias → `T\cwd\src` |
| `wp add <alias> <path>` | bookmark path as alias (30) | alias → path (absolute; relative path behavior noted) |
| `wp add .` | shorthand, same as bare (31) | identical result to bare `wp add` |
| `wp rm <alias>` | delete a bookmark (32) | alias gone from waypoint.yaml |
| `wp rm temp` | clears the temp slot (79) | temp removed |
| `wp rm` (no alias) | unspecified | documented behavior for missing arg |
| `wp ls` | list all bookmarks (33) | rich list; **no single** bare existing-path line (anti-cd, §5.1) |
| `wp set` (clipboard cleared) | clipboard → cwd → temp slot (34, 99) | temp == `T\cwd\src`, default == temp |
| `wp set` (clipboard = valid path) | clipboard wins (99) | temp == clipboard path |
| `wp set` (clipboard = invalid string) | clipboard magic (99) | documented fallback behavior |
| `wp set <alias>` | mirrors default (99) | default == alias |
| `wp set <path>` | mirrors default (99) | temp == path, default == temp |
| `wp default <alias>` | set the default bookmark (35) | `default:` == alias |
| `wp default .` | temp slot → current dir (36, 79) | temp == cwd, default == temp, existing temp overwritten |
| `wp default <path>` | temp slot → arbitrary dir (37, 79) | temp == path, default == temp |
| `wp default` (no arg) | unspecified | documented behavior for missing arg |

Prompt handling for the bare `wp add` row: L1 must pipe the name on stdin
(`"name" | python -m waypoint add`). The rich prompt text ("Bookmark name:") then
lands in *captured stdout* — that is expected, not a bug. The `wp` wrapper buffers
interactive prompts (known, AGENTS.md), so L2 must NOT assert prompt visibility.

### Configure

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp config` | show where bookmarks are stored (43) | prints storage location |
| `wp config home <path>` | store bookmarks at path (44) | waypoint.yaml created/relocated under `<path>` |
| `wp config home null` | reset, writes literal `home: null` (45, 48) | reset confirmed indirectly: with `WP_HOME` unset, `wp config` reports the project dir (reading the repo config.yaml is black-box-forbidden) |
| `WP_HOME=A` + config `home: B` | resolution order (109-112) | waypoint.yaml lives in A (env wins) |
| `WP_HOME` empty + config `home: B` | resolution order (109-112) | waypoint.yaml lives in B (config wins) |
| `WP_HOME` unset + config `home: null` | resolution order (109-112) | waypoint.yaml lives in project dir default |

Precedence probe procedure (the `T\config` fixture does NOT work — the tool reads
`config.yaml` from the project dir, which is gitignored):

1. Confirm the fixture is inert with one `wp config` run: no config under `T` is
   consulted.
2. Seed the config home through the CLI itself: `wp config home <B>` (writes the
   repo `config.yaml`), then run the three precedence rows.
3. Restore with `wp config home null`. Restoration is MANDATORY — these probes
   mutate the real, gitignored `config.yaml`. Verify indirectly via `wp config`
   with `WP_HOME` unset (must report the project dir). Do not read the file.

### Open locations (dispatch-only)

Dispatch is `os.startfile`/ShellExecute on Windows — a PATH shim (e.g. a fake
`code.cmd` earlier in `$PATH`) is NEVER invoked (verified 2026-08-04), so it cannot
intercept the shell-open. Do not attempt to mock it. Instead:

- Point the default bookmark at a sandbox path **inside `T`** so any GUI window that
  does open is confined to scratch.
- Assert exit 0 AND that the stdout confirmation line is
  `Opening <path> in Explorer` / `Opening <path> in VS Code` with `<path>` == the
  expected resolved bookmark path. That line proves resolution succeeded.
- Accept that a GUI window may briefly open; do not block on it.

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp .` | open bookmarked dir in Explorer (53) | exit 0; stdout = `Opening <path> in Explorer`; `<path>` == resolved bookmark path |
| `wp -vs` | open bookmarked dir in VS Code (54) | exit 0; stdout = `Opening <path> in VS Code`; `<path>` == resolved bookmark path |

### Help & reserved keywords

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp help` | show usage (60) | usage on stdout, exit 0 |
| `wp -h` | show usage (61) | usage on stdout, exit 0 |
| `wp -?` | listed in reserved set (73), absent from greedy list (68) and help section (60-61) | **dissonance probe:** does the command exist at all? record both ways |
| reserved-collision: `wp add add <path>` then `wp add` | reserved words beat aliases (66-71) | reserved names are REJECTED as bookmark names (`Error: '<alias>' is a reserved word and can't be a bookmark name`, exit 2 — stronger than the README guarantee); then `wp add` still runs the subcommand, never navigates |
| reserved-set sweep: each token in line 73 (`add`, `rm`, `ls`, `default`, `set`, `config`, `help`, `undo`, `u`, `history`, `h`, `.`, `-vs`, `-h`, `-?`) | closed set of keywords (71, 73) | each behaves as a keyword, none navigates as an alias |

## 5. Contracts asserted per probe

For every probe, record and check:

1. **stdout contract:** navigation = exactly one line, which must be an existing
   absolute path on disk. The anti-cd rule is the wrapper's single-line gate
   (README 157, verified): a non-navigation command must never emit a **single**
   line that is an existing path. Multi-line rich output that *includes* a bare
   path line is acceptable — e.g. `wp set` prints `Default is now temp ->` then the
   path on its own line, but the wrapper only `Set-Location`s when
   `$lines.Count -eq 1`, so no accidental cd occurs. Confirm with L2 that `$PWD`
   never changes on a non-navigation command.
2. **exit code:** success → 0. Documented failure modes → non-zero.
3. **state:** post-command re-read of YAML under `T` matches README semantics
   (bookmark added/removed, default changed, temp slot overwritten). The `home: null`
   literal in the repo config.yaml is NOT directly checkable (black-box rule) — verify
   it indirectly per §4 Configure.
4. **wrapper (L2 only):** navigation changes `$PWD`; interactive output contains ANSI
   color codes.

## 6. Dissonance taxonomy

Severity:

- **C — critical:** command does something README contradicts (wrong target / file /
  default, or errors where README implies success).
- **M — major:** output-contract breach — a **single** bare existing-path line from a
  non-navigation command (the accidental-cd trigger per §5.1), or a missing/extra path
  line that breaks the cd protocol.
- **m — minor:** cosmetic rich-output mismatch, undocumented behavior, exit-code
  drift, or a README claim with no testable surface (e.g. `-?`).

## 7. Recording: DISSONANCES.md

The protocol writes `DISSONANCES.md` in the repo root. Structure:

```markdown
# DISSONANCES.md — CLI vs README.md

Run date: <iso-timestamp>  |  Ground truth: README.md
Layers: L1 (python -m waypoint) + L2 (wp wrapper). GUI commands dispatch-only.

## Summary
- Probes executed: <n>   Passed: <n>   Dissonances: <n>
- Critical: <n>  Major: <n>  Minor: <n>

## Dissonances
## [C|M|m] <command>
- README claims: <quote> — README.md:<line>
- Observed: <stdout / exit code / state delta>
- Evidence: <exact invocation + captured transcript excerpt>
- Impact: <user-visible consequence>
- Likely owner: README | code

## Coverage
| Command | L1 | L2 | Verdict |
|---|---|---|---|
| ...     | ✓/✗ | ✓/✗ | PASS | DISSONANCE [C/M/m] |
```

- Only failures go in the Dissonances section; the Coverage table records every row.
- On a clean run (no dissonances), the file still contains the Summary + Coverage
  tables with a `Passed` count and an empty Dissonances section.

## 8. Execution checklist

1. Pre-run hygiene: `Remove-Item Env:WP_HOME` (clear any stale value), `Set-Clipboard ""`
   (clear stale clipboard), and note that the Configure section will write the repo's
   gitignored `config.yaml` (restore step is mandatory).
2. Create `T` workspace; set `WP_HOME=T\home`.
3. Warm-up: run `wp ls` on the fresh `T\home` and verify it prints the bookmark table.
   If it instead navigates (bare path) or errors, the probe harness's argument binding
   is broken (see §2 Harness rules, the `$Args` trap) — fix before proceeding.
4. Run every probe in §4 (L1), plus the `[L2]` rows through the wrapper; log each to
   `transcript.txt`.
5. Re-read YAML state under `T` after stateful probes.
6. Compare each observation against §4's "Expected" column (derived from README).
7. Classify dissonances per §6; write `DISSONANCES.md` per §7.
8. Remove `T`.
9. If any probe's behavior is ambiguous and cannot be resolved against README, record
   it as a minor dissonance rather than guessing.
