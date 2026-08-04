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
```

`wp` is always a shell `cd`. No subcommand needed.

### Manage bookmarks

```
wp add                  → bookmark current dir (prompts for name)
wp add <alias>          → bookmark current dir as <alias>
wp add <alias> <path>   → bookmark <path> as <alias>
wp add .                → bookmark current dir (shorthand, same as bare `wp add`)
wp rm <alias>           → delete a bookmark
wp ls, wp list           → list all bookmarks
wp set [alias|path]     → set default (clipboard → cwd → temp slot)
wp default <alias>      → set the default bookmark
wp default .            → point the default at the current directory (temp slot)
wp default <path>       → point the default at an arbitrary directory (temp slot)
```

### Configure

```
wp config               → show where bookmarks are stored
wp config home <path>   → store bookmarks at <path>
wp config home null     → reset to the default location
```

`null` is a literal sentinel: it writes `home: null` back into `config.yaml`, which is the documented default ("same dir as this config").

### Open locations

```
wp .        → open bookmarked dir in Explorer
wp -vs      → open bookmarked dir in VS Code
```

### Help

```
wp help     → show usage
wp -h       → show usage
```

## Design: reserved keywords vs aliases

The parser is greedy on aliases. `wp <anything>` resolves as:

1. If `<anything>` matches a **reserved keyword** (`add`, `rm`, `ls`, `list`, `default`, `set`, `config`, `help`, `.`, `-vs`, `-h`) → run the subcommand.
2. Otherwise → treat it as a bookmark alias and navigate to it.

This means `wp dev` goes to the "dev" bookmark. `wp add` runs the add subcommand. No disambiguation needed — reserved words are a small, closed set.

Reserved keywords: `add`, `rm`, `ls`, `list`, `default`, `set`, `config`, `help`, `.`, `-vs`, `-h`, `-?`

### Default bookmark

`wp` with no args navigates to the current default. `wp default <alias>` changes which bookmark is the default. The default is stored in the data file alongside bookmarks.

`wp default .` and `wp default <path>` point the default at a directory directly: they store (or overwrite) a bookmark named `temp` and make it the default — a single-slot "current directory" memory, like a scratchpad. `wp rm temp` clears it. Any existing `temp` bookmark is overwritten by design.

## Data

Two YAML files, stored at a configurable path (default: project dir `Waypoint/`). Override with `WP_HOME` env var or `wp config home <path>`.

### `waypoint.yaml` — bookmarks

```yaml
bookmarks:
  dev: "C:\\Users\\you\\dev"
  web: "C:\\Users\\you\\dev\\website"
  wp: "C:\\Users\\you\\dev\\Waypoint"
default: wp
```

`wp` (no args) navigates to the `default` bookmark. The default starts as `wp`, pointing back at the project dir itself. `wp wp` also goes there.

### `wp set`

`wp set` is a clipboard-aware shortcut for setting the default. It checks the clipboard for a valid path (paste from Explorer), falls back to cwd, and writes the result to the `temp` slot — same as `wp default .` but with clipboard magic. `wp set <alias>` and `wp set <path>` also work, mirroring `wp default`.

### `config.yaml` — tool settings

```yaml
# Where waypoint.yaml lives. Default: same dir as this config.
# Override here if you want bookmarks on a different drive / cloud-synced folder.
home: null  # null = project dir (Waypoint/)
```

Resolution order for data path:
1. `WP_HOME` env var (if set and non-empty)
2. `config.yaml` → `home` key (if non-null)
3. Default: project dir (`Waypoint/`) — `Path(__file__).resolve().parent.parent` in `waypoint/store.py`

## Stack

- Python 3.10+
- `pyperclip` — clipboard read for `wp add` with no path (paste from Explorer)
- `rich` — pretty output (lists, colors, errors)
- `pyyaml` — read/write YAML data files
- No heavy frameworks — raw `argparse` or manual argv parsing. The CLI is too simple for typer/click overhead.

## Files

```
Waypoint/
├── README.md           ← this file (the spec)
├── AGENTS.md           ← agent instructions
├── install.ps1         ← PowerShell profile installer
├── pyproject.toml      ← packaging, deps, tool config
├── .gitignore
├── .gitattributes
├── config.yaml         ← tool settings (home path, etc.)
├── waypoint.yaml       ← bookmarks + default (created & seeded on first use; not tracked)
├── waypoint/
│   ├── __init__.py
│   ├── __main__.py     ← entry point (thin: imports and calls main)
│   ├── cli.py          ← dispatch + main()
│   ├── commands.py     ← all command handlers
│   ├── prompts.py      ← interactive prompting
│   ├── constants.py    ← shared constants (exit codes, temp slot)
│   ├── output.py       ← rich output helpers
│   ├── store.py        ← read/write waypoint.yaml + config.yaml
│   └── resolver.py     ← argv parsing + reserved keyword detection
└── tests/
    ├── conftest.py       ← shared fixtures
    ├── test_store.py     ← read/write round-trips, resolution order
    ├── test_resolver.py  ← parsing, reserved keywords, alias validation
    ├── test_cli.py       ← dispatch, exit codes, wrapper protocol
    ├── test_constants.py ← constant integrity checks
    └── test_output.py    ← output helper tests
```

## Notes

- The `install.ps1` path is hardcoded to this project location. If the project moves, re-run `install.ps1`.
- The `wp` bookmark is self-referential: it points back at the project dir. This is intentional — `wp wp` = "go to waypoint itself."
- Navigation prints the resolved absolute path as the *only* stdout line; `wp` then `Set-Location`s there. Every other command prints rich-formatted output (AGENTS.md), which the wrapper re-emits — a bare existing path on stdout is the one thing that triggers a `cd`, so `wp ls` or an error can never move you.
- Colors: the wrapper sets `WP_FORCE_COLOR=1` for interactive sessions (stdout is a pipe to PowerShell, which would otherwise make rich drop color), and removes it afterwards. Plain `python waypoint/__main__.py` runs without forced color.
- `install.ps1` needs `python` on PATH; it runs `pip install -e ".[dev]"` if the import probe fails.
