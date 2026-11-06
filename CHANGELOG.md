# Changelog

## 2026-11-06#03 -- The music engine, on one engine core with video (plan step 8)

- **The music engine moved from mp3redactor** (`core/music/flow.py`, with its request cache, phase timer, time
  estimates and review rules): artist, album, genre and collection notes from MusicBrainz, Wikipedia and Discogs,
  verified by the albums really in the folder. No menu or command runs it yet: the music review page and the music
  side of Notes > Create Notes and `notes` follow (plan steps 9-10).
- **One engine core for every media type** (`core/notes_engine.py`): music and video now run, write, record in History
  and undo through the same functions, and ask Wikipedia at one pace together. What a media type's engine must
  provide is written down there.
- **Fixed:** when History was on and could not record a written video note, the write raised an error instead of
  carrying on (it called a History function this app does not have). Now the note stays written and the failure is
  logged. A test covers both media.
- Music and video share one lookup cache file; `[notes.music] kinds` remembers which music notes to make (artist notes
  by default).
- Tests: mp3redactor's ~190 engine tests moved with the engine and pass on files of this app's own (MP3 mostly); its
  tests of the review page and the command line follow with those (steps 9-10).

## 2026-11-06#02 -- Music notes: the modules moved from mp3redactor, every format read (plan steps 6-7)

- **The music notes' modules moved from mp3redactor** into `core/music/`: the folder levels (artist, album, genre,
  collections, alphabetical groupings), the title normaliser ('Seven' = '7'), match scoring, the artist test, 'Look up by
  link', the MusicBrainz and Discogs reads, the note text and 'What is in this folder'. Unchanged apart from their names.
  No menu or command uses them yet: the engine and the review page follow (plan steps 8-9).
- **Every common music format is read**, not only MP3: FLAC, M4A (AAC and ALAC), Ogg Vorbis and Opus, through mutagen
  (`core/music/tags.py`), with the cover inside the file in each format. An MP3 whose audio is damaged still gives its tags.
  Checked on files ffmpeg encoded and tagged, as well as on the tests' own.
- **Notes written by mp3redactor count as current**: same note format, so they will not be offered for a refresh.
- The review list's troubleshooting log (`core/notes_debug.py`) moved too: off by default, `FOLDERREDACTOR_NOTES_DEBUG=1`
  or `[notes] debug_log`, written next to the settings; its Preferences tick box comes with the review page.
- Tests: tiny real MP3, FLAC, M4A, Ogg and Opus files are built from bytes in `tmp_path` and tagged with mutagen (no
  encoder, no binary fixtures); mp3redactor's engine-free music tests moved with the code.

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
