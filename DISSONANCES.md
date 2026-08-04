# DISSONANCES.md — CLI vs README.md

Run date: 2026-08-04T19:52:04+02:00  |  Ground truth: README.md
Layers: L1 (python -m waypoint) + L2 (wp wrapper). GUI commands dispatch-only.
Prior run (19:36) reported 3 minor dissonances; all three were fixed and
re-probed on this run (see Methodology notes).

## Summary
- Probes executed: 38   Passed: 38   Dissonances: 0
- Critical: 0  Major: 0  Minor: 0

## Dissonances

(none)

## Coverage
| Command | L1 | L2 | Verdict |
|---|---|---|---|
| wp (no args) | y | y | PASS |
| wp <alias> | y | y | PASS |
| wp wp | y | - | PASS |
| wp <unknown-alias> | y | - | PASS |
| wp add (stdin name) | y | - | PASS |
| wp add (clipboard valid) | y | - | PASS |
| wp add (clipboard invalid) | y | - | PASS |
| wp add (clipboard empty) | y | - | PASS |
| wp add <alias> | y | - | PASS |
| wp add <alias> <path> | y | - | PASS |
| wp add . | y | - | PASS |
| wp rm <alias> | y | - | PASS |
| wp rm temp | y | - | PASS |
| wp rm (no alias) | y | - | PASS |
| wp ls / wp list | y | y | PASS |
| wp set (clipboard cleared) | y | - | PASS |
| wp set (clipboard valid) | y | - | PASS |
| wp set (clipboard invalid) | y | - | PASS |
| wp set <alias> | y | - | PASS |
| wp set <path> | y | - | PASS |
| wp default <alias> | y | - | PASS |
| wp default . | y | - | PASS |
| wp default <path> | y | - | PASS |
| wp default (no arg) | y | - | PASS |
| wp config | y | - | PASS |
| wp config home <path> | y | - | PASS |
| wp config home null | y | - | PASS |
| WP_HOME=A + config home:B | y | - | PASS |
| WP_HOME empty + config home:B | y | - | PASS |
| WP_HOME unset + config home:null | y | - | PASS |
| wp . (dispatch-only) | y | - | PASS |
| wp -vs (dispatch-only) | y | - | PASS |
| wp help | y | - | PASS |
| wp -h | y | - | PASS |
| wp -? | y | y | PASS |
| reserved-collision: wp add add | y | - | PASS |
| reserved-set sweep | y | - | PASS |

### Methodology notes (not dissonances)
- The three 19:36 dissonances were addressed before this run:
  1. `-?` is now documented in the README Help section (README.md:62) and the
     reserved-keyword list (README.md:68). Re-probed L1 (exit 0, usage on
     stdout, empty stderr) and L2 through the wrapper (exit 0).
  2. Path folding: `ok()` and `err()` now print with `soft_wrap=True`
     (waypoint/output.py), and the `Opening <path> in <app>` confirmation
     (waypoint/commands.py) likewise. Re-probed L1 under piped capture with a
     >110-char path: `Saved longp -> <path>` and `Default is now temp -> <path>`
     each emit as exactly one line (no mid-word fold). Unit tests assert the
     same under a width=20 console.
  3. Wrapper prompt buffering: the live-mode branch for `add` already existed in
     install.ps1 source (commit 29cc462) but the installed `$PROFILE` was stale;
     install.ps1 was re-run and the profile now contains the branch. L2 re-probe:
     `wp add <alias> <path>` through the wrapper exits 0 with colored output and
     writes the bookmark; `wp -?` exits 0; nav still cds to the target; `wp set`
     does not cd (anti-cd intact).
- PowerShell does not forward a pipeline into a function to a native child's
  stdin: `"name" | wp add` yields EOF in python regardless of the live branch
  (verified `GOT[]` with a bare test function). Piping a name is an L1-only
  probe technique; the interactive prompt is the documented L2 path and works
  via the console. Not a dissonance.
- config.yaml is read/written in the project dir (the repo copy, which is
  gitignored). The protocol's `T\config` fixture location cannot drive it.
  Precedence probes instead set the config home through the CLI itself
  (`wp config home <path>`) and the repo config was restored to the documented
  default (`home: null`), confirmed via `wp config` with `WP_HOME` unset.
- GUI dispatch could not be mocked: a PATH `code` shim was never invoked by
  `wp -vs`, so dispatch is via os.startfile/ShellExecute. Resolution was asserted
  through the printed "Opening <path> in Explorer / VS Code" confirmation (exit 0)
  rather than by intercepting the shell-open.
- Anti-cd letter vs spirit: add/set/default confirmations include a trailing bare
  path line, but the wrapper's single-line gate (`$lines.Count -eq 1`) is never
  satisfied by those multi-line outputs, so no accidental cd occurs (L2-verified).
