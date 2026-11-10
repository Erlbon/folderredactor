# The Ⅎolder Redactor (folderredactor)

The fifth Redactor: a tool for the folders of a media library. It drafts the Markdown folder notes the Pluteus media
server shows (`artist.md`, `album.md`, `series.md`, `about.md`), reviewed yes/no before anything is written; that is all
it does (the folder-tree clean-up of the first plan was dropped, window review 2026-11-10). What a user sees is in
[ABOUT.md](ABOUT.md); this file is for working on the code.

Status: plan steps 5-11 (step 11: the full check, 2026-11-06), then the window of the review of 2026-11-10
(`docs/ui-review-2026-11-10.md`): the library as a tree with a note light per folder on the left, the note pane always
open on the right, Look Up on the selected folder in the background. Look Up and the `notes` command work for music
(moved from mp3redactor: `core/music/`, MP3, FLAC, M4A, Ogg and Opus through mutagen) and video (from videoredactor:
`core/video/`), told apart by the folder's files (`core/media_guess.py`). Both run through one engine core
(`core/notes_engine.py`); the matching controls are redactor_common's `ProposalPanel`, music's extras switched on
through `ReviewHooks` (`gui/music_notes.py`). File > Import takes over the old apps' notes settings, lookup cache and
API keys (`core/old_apps.py`).

## Running and testing

```
python ../redactor-build-tools/devenv/venv_sync.py .   # this repo's own .venv at the redactor_common pin (never pip
                                                       # install -r requirements.txt into the shared Python)
.venv\Scripts\python main.py              # the window
.venv\Scripts\python main.py D:\Music     # the window with that library open
.venv\Scripts\python main.py --help       # the command line (one exe, see foldercli/)
.venv\Scripts\python -m pytest            # tests/ (Qt runs offscreen), as the pre-push hook does
.venv\Scripts\python bump_version.py      # with every code commit, plus a CHANGELOG.md entry
build_exe.bat                             # dist\folderredactor.exe and dist\folderredactor-setup.exe (Windows, Inno
                                          # Setup 6), built with the .venv
.venv\Scripts\python -m redactor_common.release manifest   # dist\update-manifest.json from the built files
```

Releases go through the family's update framework (redactor_common `docs/update-framework.md`): `pyproject.toml`'s
`[tool.redactor-release]` says what is built and published, `installer/folderredactor.iss` includes the shared
installer contract at its end, and each build declares its update channel (`folderredactor.spec`).
`.venv\Scripts\python -m redactor_common.release publish` builds, publishes a pre-release, runs the update gate and only
then makes it Latest. The first release on the framework needs `--first-framework-release`.

After cloning, switch the hooks on once: `git config core.hooksPath .githooks` (pre-commit: staged files parse and
hold no control characters; pre-push: the tests pass).

## Layout

| Path | What |
| --- | --- |
| `main.py` | Entry point: the command line when the first argument is a command, otherwise the window |
| `core/__init__.py` | Configures redactor_common's shared lookup clients (User-Agent, key store) for this app |
| `core/version.py` | `APP_NAME` (the turned F written as `"\u2132"`), `APP_VERSION` (set by `bump_version.py`) |
| `core/app_paths.py` | Where the app's own files live: next to the exe, never in a library |
| `core/settings.py` | `folderredactor_settings.ini`, File > Recent |
| `core/api_keys.py` | Discogs token and TMDB key: the Redactor family's shared keys (redactor_common `secret_store.get_key`; this app's own old entry `folderredactor` is the fallback) |
| `core/history.py` | Tools > History: the shared journal, opt-in, with the note-undo handlers |
| `core/notes_engine.py` | The one engine core of every media type: the run loop, write, History record, undo, summary, the shared Wikipedia fetch; and what an engine must provide |
| `core/notes_settings.py` | What Look Up remembers for every media type (`[notes]`), the lookup cache's place |
| `core/video/` | Video notes (from videoredactor): `local` (which folders), `tmdb`, `render`, `flow` (the engine), `settings` (`[notes.video]`) |
| `core/music/` | Music notes (from mp3redactor): `flow` (the engine), `tags` (mutagen reader, every format), `local`, `numbers`, `match`, `level`, `kinds`, `link`, `musicbrainz`, `discogs`, `cache` (Discogs wrapper), `phases`, `timing`, `review`, `render`, `evidence`, `settings` (`[notes.music]`) |
| `core/notes_debug.py` | The opt-in troubleshooting log of the review list (off by default) |
| `gui/main_window.py` | The window: the tree and the note pane side by side, Look Up, ticks and writing, editing, Undo, the family's menu skeleton |
| `gui/library_tree.py` | The library tree: folders listed when opened, the note state of each read by a background thread, lights and tick boxes |
| `gui/lights.py` | The note lights (shape and colour: ● note, ◐ waiting, ✎ edited, ○ none) |
| `gui/note_pane.py` | The note pane: header, the Match strip (`MatchStrip`, redactor_common's `ProposalPanel` with only its matching controls), Preview / Raw / Before-after, Edit / Save |
| `gui/lookup_worker.py` | The one lookup thread: scans and lookups of a Look Up, and the rebuilds after a person's choice (first in line); one engine per media type per library |
| `core/media_guess.py` | Music or video library, from a bounded look at the file names |
| `core/old_apps.py` | File > Import from mp3redactor or videoredactor: their notes settings and lookup cache (from the folder pointed at), their API keys (by name in the credential store, offered once at start-up) |
| `gui/music_notes.py` | Music's part of the window: the Look Up kinds, the `ReviewHooks` of the Match strip (levels, link, genres, best guesses, log), the engine |
| `gui/music_evidence_view.py` | The Local files under the tree: cover thumbnail, tracks, tags (read in the background, cached) |
| `gui/video_notes.py` | Video's part of the window: the Look Up kinds, the TMDB key check, the engine |
| `gui/api_keys_dialog.py`, `gui/preferences_dialog.py` | Tools > API Keys, Tools > Preferences |
| `foldercli/` | The command line (`COMMANDS`, `main.py`, `cmd_notes.py`: one `notes` for music and video, `--media auto`) |
| `tests/` | pytest; every test keeps its settings, journal and keys in `tmp_path`. `tests/music_helpers.py` builds tiny real MP3 / FLAC / M4A / Ogg / Opus files from bytes and tags them with mutagen (no encoder, no binary fixtures); `tests/notes_gui_helpers.py` drives Look Up through the real window (the music and video window-flow tests) |

## Rules this app keeps

- Into a library it writes `.md` folder notes and nothing else.
- Nothing is written without a yes, and everything written is undoable from Tools > History (Edit > Undo for the last one).
- It follows the family conventions in full (see CLAUDE.md): version bump + CHANGELOG with every code commit, the
  menu skeleton and its lint, progress dialogs for slow work, the CLI inside the one exe.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
