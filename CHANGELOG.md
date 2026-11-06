# Changelog

## 2026-11-06#01 -- Folder notes for video libraries (moved from videoredactor)

- **Notes > Create Notes works for video libraries**: `series.md` in a series folder, `about.md` in a film folder,
  from TMDB and (only when Wikidata links it to the title's IMDb id) a Wikipedia introduction, reviewed yes/no on
  the shared review page before anything is written. The engine, its rules and its tests moved from videoredactor
  unchanged (`core/video/`, `gui/video_notes.py`); music notes come with a later step.
- **The `notes` command** on the command line, with videoredactor's options (`--write`, `--kind`, `--update`,
  `--include-uncertain` and the rest). ABOUT.md documents it.
- **Films in any common container count**: `.avi`, `.mov`, `.wmv`, `.webm`, `.mpg`, `.ts` and others, not only the
  `.mp4`/`.m4v`/`.mkv` videoredactor can tag. This app only counts videos, it never opens one.
- **Notes written by videoredactor count as current**: same note format, so they are not offered for a refresh.
- **Tools > Clear Lookup Cache** works, and **Tools > Preferences** has the Create Notes switches (lookup cache,
  Wikipedia introduction).
- A refresh of an old note on a drive without a Recycle Bin (a network share) keeps the old note and reports the
  write as failed: this app has no backup-folder setting yet.
- **redactor_common 2026-11-06-01** (was 2026-11-05-01), the family's one pin: folder scans skip junctions, and
  menu items no longer pass `checked` into slots with an optional first parameter.

## 2026-11-05#01 -- redactor_common 2026-11-05-01

- **redactor_common 2026-11-05-01** (was 2026-11-04-02), the family's one pin. Undo keeps 50 steps (was 5), and
  the shared Redact engine has a dry run; neither changes anything here yet (no Redact, no undoable edits).

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
