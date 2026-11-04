# Changelog

## 2026-11-04#02 -- redactor_common 2026-11-04-02, and tests in the repo's own venv

- **redactor_common 2026-11-04-02** (was 2026-11-04-01), the tag the other Redactors use. The family keeps one pin
  from now on.
- **The pre-push hook tests in this repo's own `.venv`**, made and kept at the pin by
  `redactor-build-tools/devenv/venv_sync.py`. With one shared install, one repo's pin broke the others' pushes.
  `tests/test_pre_push_hook.py` guards the hook; `.venv/` is ignored.

## 2026-11-04#01 -- First skeleton

The Ⅎolder Redactor starts as its own app (plan: Create Notes moves out of mp3redactor and videoredactor, and the
folder-tree clean-up joins it). Built from videoredactor's skeleton; nothing of the two jobs works yet.
- The window: File > Open Library Folder (Ctrl+Shift+O), File > Recent, a folder dropped on the window or given on
  the command line.
- The family's menu skeleton with every menu of the plan: File, Edit, View, Notes, Clean Up, Tools, Help, and the
  Ctrl+K command palette. Notes and Clean Up are shown greyed until their steps are built.
- Tools > API Keys (Discogs token, TMDB key, in the credential store), Tools > History (opt-in, off by default),
  Tools > Preferences (History on/off and Delete History, the daily update check), Help (Changelog, Credits, Check
  for Updates, About).
- The command line in the one exe, with no commands yet.
- Uses the shared lookup clients of redactor_common 2026-11-04#01 (`core/lookups/`).
