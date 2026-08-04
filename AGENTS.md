# Agent Instructions

Use `rich` to color all output that will be read by an end user.

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
