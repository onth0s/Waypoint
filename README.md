# Waypoint

A path-bookmark CLI. Type less, get there faster.

## Install

```powershell
cd "C:\Users\you\dev\Waypoint"
.\install.ps1
```

Adds a `wp` function to your PowerShell `$PROFILE`. The installer uses `pip install -e ".[dev]"` to install runtime deps plus dev tools (pytest, ruff).

## Usage

### Navigate

```
wp              → go to default bookmark
wp <alias>      → go to bookmark named <alias>
wp undo [N]     → go to history row N (0 = current dir, 1 = last jump; default 1)
wp history [N]  → show the last N directories (incl. current; default 5)
wp history --all → show the full navigation history
```

`wp` is always a shell `cd`. No subcommand needed.

Every directory change records where you *came from* **and** where you *arrived*
(both deduped), so the newest persistent history entry is always the current
directory. `wp history` (alias `wp h`) lists the newest entries, newest first,
starting at row 0 = the current dir, so row N matches `wp undo N`. Because the
current dir is persisted, a **fresh tab** can run `wp h` and `wp u 0` to land
instantly where the last tab was. Stale, deleted dirs are skipped. `wp h --all`
(also `--full`, `full`, `all`, `f`, `a`) shows the whole stack. The stack is
capped at 50 entries (`UNDO_STACK` in `waypoint/constants.py`); the default
window size is `HISTORY_PREVIEW` (5).

### Manage bookmarks

```
wp add                  → bookmark current dir (prompts for name)
wp add <alias>          → bookmark current dir as <alias>
wp add <alias> <path>   → bookmark <path> as <alias>
wp add .                → bookmark current dir (shorthand, same as bare `wp add`)
wp rm <alias>           → delete a bookmark
wp ls, wp list           → list all bookmarks
wp set [alias|path|~]   → set default (clipboard → cwd → temp slot; `~` resolves to home)
wp default <alias>      → set the default bookmark
wp default .            → point the default at the current directory (temp slot)
wp default <path|~>     → point the default at an arbitrary directory or home (temp slot)
```

### Configure

```
wp store                 → show where bookmarks are stored
wp store <alias|path|~>  → store bookmarks at <alias> target or <path> (auto-creates directory if missing)
wp config                → show where bookmarks are stored
wp config home <path>    → store bookmarks at <path>
wp config home null      → reset to the default location
```

`null` is a literal sentinel: it writes `home: null` back into `config.yaml`, which is the documented default ("same dir as this config"). `wp store ~` sets the bookmark storage directory directly to your home directory (`~`).

### Open locations

```
wp .        → open bookmarked dir in Explorer
wp -vs      → open bookmarked dir in VS Code
```

### Help

```
wp help     → show usage
wp -h       → show usage
wp -?       → show usage
```

## Design: reserved keywords vs aliases

The parser is greedy on aliases. `wp <anything>` resolves as:

1. If `<anything>` matches a **reserved keyword** (`add`, `rm`, `ls`, `list`, `default`, `set`, `store`, `config`, `help`, `undo`, `u`, `history`, `h`, `.`, `-vs`, `-h`, `-?`) → run the subcommand.
2. Otherwise → treat it as a bookmark alias and navigate to it.

This means `wp dev` goes to the "dev" bookmark. `wp add` runs the add subcommand. No disambiguation needed — reserved words are a small, closed set.

Reserved keywords: `add`, `rm`, `ls`, `list`, `default`, `set`, `store`, `config`, `help`, `undo`, `u`, `history`, `h`, `.`, `-vs`, `-h`, `-?` (plus `_record_history`, reserved for internal wrapper use)

### Default bookmark

`wp` with no args navigates to the current default. `wp default <alias>` changes which bookmark is the default. The default is stored in the data file alongside bookmarks.

`wp default .` and `wp default <path>` point the default at a directory directly: they store (or overwrite) a bookmark named `temp` and make it the default — a single-slot "current directory" memory, like a scratchpad. `wp rm temp` clears it. Any existing `temp` bookmark is overwritten by design.

## Data

Two YAML files (`waypoint.yaml` and `history.yaml`), stored at a configurable path (default: `~/.waypoint`). Override with `WP_HOME` env var or `wp config home <path>` (which writes `config.yaml` in the project dir).

### `waypoint.yaml` — bookmarks

```yaml
bookmarks:
  dev: "C:\\Users\\you\\dev"
  web: "C:\\Users\\you\\dev\\website"
  wp: "C:\\Users\\you\\dev\\Waypoint"
default: wp
```

`wp` (no args) navigates to the `default` bookmark. The default starts as `wp`, pointing back at the project dir itself. `wp wp` also goes there.

### `history.yaml` — navigation history

```yaml
- "C:\\Users\\you\\dev\\website"
- "C:\\Users\\you\\dev"
```

The most recent directories, oldest first (the newest entry is the current dir,
or the last tab's dir in a fresh shell). Every location change records both the
dir you left and the dir you arrived at, automatically deduped, so a new tab can
`wp u 0` back to where the last one was. Missing file = empty history. Written
atomically alongside `waypoint.yaml` and trimmed to the newest 50 entries; the
CLI's undo walks it newest-first.

### `wp set`

`wp set` is a clipboard-aware shortcut for setting the default. It checks the clipboard for a valid path (paste from Explorer), falls back to cwd, and writes the result to the `temp` slot — same as `wp default .` but with clipboard magic. `wp set <alias>` and `wp set <path>` also work, mirroring `wp default`.

### `config.yaml` — tool settings

```yaml
# Where waypoint.yaml lives. Default: same dir as this config.
# Override here if you want bookmarks on a different drive / cloud-synced folder.
home: null  # null = default (~/.waypoint)
```

Resolution order for data path:
1. `WP_HOME` env var (if set and non-empty)
2. `config.yaml` → `home` key (if non-null)
3. Default: `~/.waypoint` — `Path.home() / ".waypoint"` in `waypoint/store.py` (`config.yaml` with `home: null` resolves to `~/.waypoint`)

## Stack

- Python 3.10+
- `pyperclip` — clipboard read for `wp add` with no path (paste from Explorer)
- `rich` — pretty output (lists, colors, errors)
- `pyyaml` — read/write YAML data files
- No heavy frameworks — raw `argparse` or manual argv parsing. The CLI is too simple for typer/click overhead.

## Files

```
Waypoint/
├── README.md                 ← this file (the spec)
├── AGENTS.md                 ← agent instructions
├── install.ps1               ← PowerShell profile installer
├── pyproject.toml            ← packaging, deps, tool config
├── .gitignore
├── .gitattributes
├── config.yaml               ← tool settings (home path, etc.; not tracked)
├── waypoint.yaml             ← bookmarks + default (created & seeded on first use; not tracked)
├── history.yaml              ← navigation history (created & updated by every wp jump; not tracked)
├── misc/INSPECTOR.md         ← black-box conformance protocol against this README
├── misc/REFACTORING_PLAN.md  ← codebase audit & sequential refactoring plan
├── scripts/
│   └── check.ps1             ← unified quality check runner (ruff + mypy + pytest)
├── waypoint/
│   ├── __init__.py
│   ├── __main__.py           ← entry point (thin: imports and calls main)
│   ├── cli.py                ← dispatch + main()
│   ├── clipboard.py          ← clipboard helper utilities
│   ├── commands/             ← command handler package
│   │   ├── __init__.py
│   │   ├── nav.py            ← navigation handlers (_nav, _record_origin)
│   │   ├── history.py        ← history & undo handlers (_undo, _history)
│   │   ├── bookmarks.py      ← bookmark management (_add, _rm, _ls, _default, _set)
│   │   ├── config.py         ← configuration handler (_config)
│   │   └── launcher.py       ← external app launcher & help (_open, _help)
│   ├── prompts.py            ← interactive prompting
│   ├── constants.py          ← shared constants (exit codes, temp slot, history caps)
│   ├── output.py             ← rich output helpers
│   ├── store.py              ← read/write waypoint.yaml + history.yaml + config.yaml
│   └── resolver.py           ← argv parsing + reserved keyword detection
└── tests/
    ├── conftest.py               ← shared fixtures
    ├── test_store.py             ← read/write round-trips, resolution order
    ├── test_resolver.py          ← parsing, reserved keywords, alias validation
    ├── test_cli.py               ← dispatch, exit codes, wrapper protocol
    ├── test_nav_commands.py      ← navigation command unit tests
    ├── test_bookmark_commands.py ← bookmark management command unit tests
    ├── test_constants.py         ← constant integrity checks
    ├── test_output.py            ← output helper tests
    ├── test_wrapper_contract.py  ← wrapper coupling & interactive command contract tests
    └── test_commands_exports.py  ← package export hygiene tests
```

## Development & Quality Checks

Run all quality gates (linting, static type checking, unit tests):

```powershell
.\scripts\check.ps1
```

Or run individually:
- `python -m ruff check .`
- `python -m mypy waypoint`
- `python -m pytest -q`

## Notes

- The `install.ps1` path is hardcoded to this project location. If the project moves, re-run `install.ps1`.
- The installer also overrides the built-in `cd`/`chdir` aliases with `Set-WaypointLocation`, so plain directory changes (including `cd -`, which toggles to the previous location) feed an in-session history, `$global:WpHistory`. The no-space shortcuts `cd..`, `cd~`, and `cd\` are single tokens PowerShell resolves to native `Set-Location` (bypassing the alias), so the wrapper defines same-named functions that route them through the same recorder. `wp` jumps route through the same wrapper. `cdh` prints the session history. That stack is session-local; `wp undo`/`wp history` read the persistent `history.yaml` stack instead (which is fed the same way and, since the wrapper records both the dir left and the dir arrived at, always has the current dir on top).
- The `wp` bookmark is self-referential: it points back at the project dir. This is intentional — `wp wp` = "go to waypoint itself."
- Navigation prints the resolved absolute path as the *only* stdout line; `wp` then `Set-Location`s there. Every other command prints rich-formatted output (AGENTS.md), which the wrapper re-emits — a bare existing path on stdout is the one thing that triggers a `cd`, so `wp ls` or an error can never move you.
- Colors: the wrapper sets `WP_FORCE_COLOR=1` for interactive sessions (stdout is a pipe to PowerShell, which would otherwise make rich drop color), and removes it afterwards. Plain `python waypoint/__main__.py` runs without forced color.
- `install.ps1` needs `python` on PATH; it runs `pip install -e ".[dev]"` if the import probe fails.
- `PROJECT_DIR` in `store.py` locates `config.yaml` relative to the installed package path (`Path(__file__).resolve().parent.parent`). Waypoint requires installation in editable mode (`pip install -e .`).


