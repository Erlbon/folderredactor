# The Ⅎolder Redactor (folderredactor)

The fifth Redactor: a tool for the folders of a media library. Job 1 drafts the Markdown folder notes the Pluteus
media server shows (`artist.md`, `album.md`, `series.md`, `about.md`), reviewed yes/no before anything is written.
Job 2 checks a library's folder tree against its conventions and renames only what is said yes to, with undo. What
a user sees is in [ABOUT.md](ABOUT.md); this file is for working on the code.

Status: skeleton (plan step 4). The window, the menus (Notes and Clean Up greyed), API Keys, History, Preferences,
Help and an empty command line are in place.

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
| `gui/main_window.py` | The window and the family's menu skeleton |
| `gui/api_keys_dialog.py`, `gui/preferences_dialog.py` | Tools > API Keys, Tools > Preferences |
| `foldercli/` | The command line (`COMMANDS`, `main.py`); no commands yet |
| `tests/` | pytest; every test keeps its settings, journal and keys in `tmp_path` |

## Rules this app keeps

- Into a library it writes `.md` folder notes and nothing else.
- Nothing is written or renamed without a yes, and everything written is undoable from Tools > History.
- It follows the family conventions in full (see CLAUDE.md): version bump + CHANGELOG with every code commit, the
  menu skeleton and its lint, progress dialogs for slow work, the CLI inside the one exe.

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
