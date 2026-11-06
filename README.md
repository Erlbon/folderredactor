# The Ⅎolder Redactor (folderredactor)

The fifth Redactor: a tool for the folders of a media library. Job 1 drafts the Markdown folder notes the Pluteus
media server shows (`artist.md`, `album.md`, `series.md`, `about.md`), reviewed yes/no before anything is written.
Job 2 checks a library's folder tree against its conventions and renames only what is said yes to, with undo. What
a user sees is in [ABOUT.md](ABOUT.md); this file is for working on the code.

Status: plan steps 5-10. Notes > Create Notes and the `notes` command work for music (moved from mp3redactor:
`core/music/`, MP3, FLAC, M4A, Ogg and Opus through mutagen) and video (from videoredactor: `core/video/`); the window
and the command line tell them apart by the library's files (`core/media_guess.py`). Both run through one engine core
(`core/notes_engine.py`) and one review page, redactor_common's, whose template is mp3redactor's page; music switches
its extras on through `ReviewHooks` (`gui/music_notes.py`). File > Import takes over the old apps' notes settings,
lookup cache and API keys (`core/old_apps.py`). The Clean Up menu is still greyed.

## Running and testing

```
pip install -r requirements.txt
python main.py                 # the window
python main.py D:\Music        # the window with that library open
python main.py --help          # the command line (one exe, see foldercli/)
pytest                         # tests/ (Qt runs offscreen)
python bump_version.py         # with every code commit, plus a CHANGELOG.md entry
build_exe.bat                  # dist\folderredactor.exe (Windows)
```

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
| `core/api_keys.py` | Discogs token and TMDB key in the credential store (app `folderredactor`) |
| `core/history.py` | Tools > History: the shared journal, opt-in, with the note-undo handlers |
| `core/notes_engine.py` | The one engine core of every media type: the run loop, write, History record, undo, summary, the shared Wikipedia fetch; and what an engine must provide |
| `core/notes_settings.py` | What Create Notes remembers for every media type (`[notes]`), the lookup cache's place |
| `core/video/` | Video notes (from videoredactor): `local` (which folders), `tmdb`, `render`, `flow` (the engine), `settings` (`[notes.video]`) |
| `core/music/` | Music notes (from mp3redactor): `flow` (the engine), `tags` (mutagen reader, every format), `local`, `numbers`, `match`, `level`, `kinds`, `link`, `musicbrainz`, `discogs`, `cache` (Discogs wrapper), `phases`, `timing`, `review`, `render`, `evidence`, `settings` (`[notes.music]`) |
| `core/notes_debug.py` | The opt-in troubleshooting log of the review list (off by default) |
| `gui/main_window.py` | The window and the family's menu skeleton |
| `core/media_guess.py` | Music or video library, from a bounded look at the file names |
| `core/old_apps.py` | File > Import from mp3redactor or videoredactor: their notes settings and lookup cache (from the folder pointed at), their API keys (by name in the credential store, offered once at start-up) |
| `gui/music_notes.py` | Music's hook on redactor_common's scope question, run and review page (its `ReviewHooks`: levels, link, genres, Local files, best guesses, album follow-up, log) |
| `gui/music_evidence_view.py` | The review page's Local files tab: cover thumbnail, tracks, tags (read in the background, cached) |
| `gui/video_notes.py` | Video's hook on redactor_common's scope question, run and review page |
| `gui/api_keys_dialog.py`, `gui/preferences_dialog.py` | Tools > API Keys, Tools > Preferences |
| `foldercli/` | The command line (`COMMANDS`, `main.py`, `cmd_notes.py`: one `notes` for music and video, `--media auto`) |
| `tests/` | pytest; every test keeps its settings, journal and keys in `tmp_path`. `tests/music_helpers.py` builds tiny real MP3 / FLAC / M4A / Ogg / Opus files from bytes and tags them with mutagen (no encoder, no binary fixtures); `tests/notes_gui_helpers.py` drives Notes > Create Notes through the real window (the music and video window-flow tests) |

## Rules this app keeps

- Into a library it writes `.md` folder notes and nothing else.
- Nothing is written or renamed without a yes, and everything written is undoable from Tools > History.
- It follows the family conventions in full (see CLAUDE.md): version bump + CHANGELOG with every code commit, the
  menu skeleton and its lint, progress dialogs for slow work, the CLI inside the one exe.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
