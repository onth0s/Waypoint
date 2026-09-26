# Agent Instructions

Use `rich` (`rich.console.Console`, `rich.table.Table`, `rich.panel.Panel`, `rich.text.Text`) for all user-facing CLI logs, status messages, table outputs, and error/warning prompts to maintain vibrant, high-contrast, structured styling across terminal outputs.

## File Access & Workspace Isolation

- **NEVER create, modify, write to, or delete any file outside the project repository directory.** All temporary files, test stores, scratch files, and refactoring scripts MUST remain strictly contained within the project directory or virtual test fixtures (`tmp_path`). Never mutate user home files (`~`), system user profiles, or external data files directly.

## Git Branching

- **NEVER work directly on `master`.** All agent changes, features, refactorings, and fixes MUST be made and committed on the `dev` branch. Never commit or push to `master`.

## Fuckups

- Unicode in rich output crashes. The `wp` wrapper captures stdout through a pipe,
  so Python encodes it with the Windows ANSI code page (cp1252), which lacks
  `\u2192` (->) and mangles `\u2014`. Result: `UnicodeEncodeError` tracebacks on
  `wp set`, `wp help`, `wp add`, `wp rm`. Fix: user-facing output is ASCII-only.
  No `\uXXXX` escapes in rich strings; use `->`, `--`, `*`. README may keep
  unicode (it's docs, not runtime output).

- Interactive prompts vanish through the wrapper. The `wp` function captures
  stdout with `@(...)`, so a rich `Prompt.ask` (e.g. `wp add`'s "Bookmark name:")
  is buffered until the command finishes and the user types blind. Fix: the
  wrapper runs prompting commands live (no `@()` capture) via an explicit list
  in install.ps1. Any new command that prompts interactively MUST be added to
  that list, or it will get the same invisible-prompt bug.

- Prompting and navigating are mutually exclusive in one process. Making a
  prompt visible requires running live (uncaptured stdout); making the `cd`
  work requires capturing stdout to read the bare path off it. A live process
  cannot do both. `wp <alias> -F` (create a missing target dir) resolves this
  with the `WP_NAV_OUT` side channel: the wrapper exports a temp file path, the
  CLI writes the resolved path there instead of stdout, and the wrapper reads
  it, `Set-Location`s, and deletes it. Two rules follow. Any new *prompting
  navigation* path needs that side channel, not a second stdout line. And
  `WP_NAV_OUT` is a Python<->PowerShell contract -- renaming it on one side only
  fails silently, with the CLI quietly falling back to stdout that nobody reads.
  `tests/test_wrapper_contract.py` guards both.

- `rich.Confirm` renders `[y/n]` followed by a redundant `(n)`, not the
  conventional `[y/N]`. `prompt_name`'s sibling `_YesNo` in `waypoint/prompts.py`
  overrides `make_prompt` to capitalize the default letter. Override
  `make_prompt`; do not try to pass `show_default=False` (not a `__call__` kwarg
  in rich 15) and do not uppercase `Confirm.choices` (`process_response`
  lowercases input, so `"n"` would stop matching and every decline would
  re-prompt).
