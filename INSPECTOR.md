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
  config/     only for precedence probes: config.yaml with home: <B>
  out.txt     captured stdout
  err.txt     captured stderr
  transcript.txt   full probe log (command + exit code + outputs)
```

Rules:

- Every probe sets `WP_HOME=T\home` (unless a probe is specifically testing the
  resolution order without it — then it is unset/empty).
- Seed bookmarks only through the CLI itself (black box), never by hand-writing YAML,
  except for the config.yaml fixture used in precedence probes.
- cwd-dependent probes (`wp add` bare, `wp set`, `wp default .`) run with cwd = `T\cwd\src`.
- At the end, delete `T`.

## 3. Invocation layers

Both layers are exercised per the protocol owner's decision.

- **L1 — raw core (authoritative for stdout / exit / state contracts):**
  `python -m waypoint <args>` with `WP_HOME=T\home`, cwd = probe cwd.
  Capture with:

  ```powershell
  & python -m waypoint @args 1>out.txt 2>err.txt
  $code = $LASTEXITCODE
  ```

- **L2 — wrapper (`wp` function):** a fresh `pwsh` that loads the `wp` function from
  `$PROFILE`, runs `wp <args>`, and asserts:
  - navigation commands changed `$PWD` to the resolved absolute path (the `cd`),
  - interactive output is colorized (ANSI codes present) because the wrapper forces
    color — verify with `wp ls` and inspect the captured output for escape sequences.

  README's cd contract (line 157): *a bare existing path on stdout is the one thing
  that triggers a `cd`.* L1 proves the bare path line is emitted; L2 proves the
  wrapper turns it into a `Set-Location`.

## 4. Full command matrix

Run **every** row. L1 on all rows; L2 on the rows marked `[L2]`.

### Navigation

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp` (no args) | go to default bookmark (18, 95) | exit 0; stdout = exactly one line = resolved absolute path of default |
| `wp <alias>` | go to bookmark named alias (20) | exit 0; stdout = resolved absolute path of alias |
| `wp wp` | self-referential → project dir (95, 156) | exit 0; stdout = project dir path |
| `wp <unknown-alias>` | only reserved words run subcommands (68-71) | non-zero exit; **no** bare existing path on stdout (must never cd) |
| `wp <alias>` where alias exists | — | L2: `$PWD` == resolved path |

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
| `wp ls` | list all bookmarks (33) | rich list; **no** bare path line (anti-cd) |
| `wp set` (clipboard cleared) | clipboard → cwd → temp slot (34, 99) | temp == `T\cwd\src`, default == temp |
| `wp set` (clipboard = valid path) | clipboard wins (99) | temp == clipboard path |
| `wp set` (clipboard = invalid string) | clipboard magic (99) | documented fallback behavior |
| `wp set <alias>` | mirrors default (99) | default == alias |
| `wp set <path>` | mirrors default (99) | temp == path, default == temp |
| `wp default <alias>` | set the default bookmark (35) | `default:` == alias |
| `wp default .` | temp slot → current dir (36, 79) | temp == cwd, default == temp, existing temp overwritten |
| `wp default <path>` | temp slot → arbitrary dir (37, 79) | temp == path, default == temp |
| `wp default` (no arg) | unspecified | documented behavior for missing arg |

### Configure

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp config` | show where bookmarks are stored (43) | prints storage location |
| `wp config home <path>` | store bookmarks at path (44) | waypoint.yaml created/relocated under `<path>` |
| `wp config home null` | reset, writes literal `home: null` (45, 48) | config.yaml contains `home: null` |
| `WP_HOME=A` + config `home: B` | resolution order (109-112) | waypoint.yaml lives in A (env wins) |
| `WP_HOME` empty + config `home: B` | resolution order (109-112) | waypoint.yaml lives in B (config wins) |
| `WP_HOME` unset + config `home: null` | resolution order (109-112) | waypoint.yaml lives in project dir default |

### Open locations (dispatch-only — no GUI is launched)

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp .` | open bookmarked dir in Explorer (53) | resolves bookmarked dir and dispatches to Explorer; use a wrapper mock intercepting the shell-open so no GUI spawns; assert resolution succeeded |
| `wp -vs` | open bookmarked dir in VS Code (54) | same dispatch mock for VS Code |

### Help & reserved keywords

| Probe | README claim (line ref) | Expected (per README) |
|---|---|---|
| `wp help` | show usage (60) | usage on stdout, exit 0 |
| `wp -h` | show usage (61) | usage on stdout, exit 0 |
| `wp -?` | listed in reserved set (73), absent from greedy list (68) and help section (60-61) | **dissonance probe:** does the command exist at all? record both ways |
| reserved-collision: `wp add add <path>` then `wp add` | reserved words beat aliases (66-71) | `wp add` runs subcommand, never navigates |
| reserved-set sweep: each token in line 73 (`add`, `rm`, `ls`, `default`, `set`, `config`, `help`, `.`, `-vs`, `-h`, `-?`) | closed set of keywords (71, 73) | each behaves as a keyword, none navigates as an alias |

## 5. Contracts asserted per probe

For every probe, record and check:

1. **stdout contract:** navigation = exactly one line, which must be an existing
   absolute path on disk. Every non-navigation command must NOT emit a bare existing
   path line (the anti-cd rule, README 157).
2. **exit code:** success → 0. Documented failure modes → non-zero.
3. **state:** post-command re-read of YAML under `T` matches README semantics
   (bookmark added/removed, default changed, temp slot overwritten, `home: null`
   literal written).
4. **wrapper (L2 only):** navigation changes `$PWD`; interactive output contains ANSI
   color codes.

## 6. Dissonance taxonomy

Severity:

- **C — critical:** command does something README contradicts (wrong target / file /
  default, or errors where README implies success).
- **M — major:** output-contract breach — a bare path line where README forbids it, or
  a missing/extra path line that breaks the cd protocol.
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

1. Create `T` workspace; set `WP_HOME=T\home`.
2. Run every probe in §4 (L1), plus the `[L2]` rows through the wrapper; log each to
   `transcript.txt`.
3. Re-read YAML state under `T` after stateful probes.
4. Compare each observation against §4's "Expected" column (derived from README).
5. Classify dissonances per §6; write `DISSONANCES.md` per §7.
6. Remove `T`.
7. If any probe's behavior is ambiguous and cannot be resolved against README, record
   it as a minor dissonance rather than guessing.
