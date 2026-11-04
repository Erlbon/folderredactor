# folderredactor

The Ⅎolder Redactor (`APP_NAME` "The \u2132older Redactor", Ⅎ = U+2132 TURNED CAPITAL F): a PyQt6 Windows desktop tool for the folders of a media library, with two jobs: drafting the Markdown folder notes Pluteus shows (moved out of mp3redactor and videoredactor), and checking a library's folder tree against its conventions with yes/no renames (ideas from comic-checker, written fresh). Part of the Redactor family; shared code lives in [redactor_common](https://github.com/Erlbon/redactor_common), pinned by tag in `requirements.txt`. The plan: `C:\Temp\Claude\notes-app-plan\plan.md`.

## Commands
- Run: `pip install -r requirements.txt` then `python main.py` (or `python main.py D:\Music` to open a library)
- Test: `pytest` (tests in `tests/`, Qt offscreen)
- Build exe: `build_exe.bat` (`folderredactor.spec`). It must be built on Windows.
- Bump version: `python bump_version.py`
- Hooks: `git config core.hooksPath .githooks` once per clone (pre-commit: staged files parse, no control characters; pre-push: the tests pass)

## Domain notes
- **Into a library this app writes `.md` folder notes and nothing else.** No settings, cache, report, log, backup, marker or index in a library tree: they live next to the exe (`core/app_paths.py`) or where `--output` points. The clean-up's renames change names, they add nothing.
- Nothing is written without a yes: notes are reviewed (shared `NotesReviewDialog`), renames are reviewed (Renames tab), and both are undoable from Tools > History. History is opt-in (off by default).
- The lookup clients are redactor_common's `core/lookups/` (MusicBrainz, Discogs, TMDB, release names, folder covers) and `core/wikipedia.py`; `core/__init__.py` configures them with this app's User-Agent and key store (`core/api_keys.py`, app name `folderredactor`).
- Write `APP_NAME`'s turned F as the escape `"\u2132"` in code, never pasted through a heredoc or a patch script.
- Every new CLI command goes into `foldercli.COMMANDS` and the "Command line" section of ABOUT.md (tests/test_cli.py checks both).

## Family conventions (apply to every Redactor repo)
1. **Sync first.** Other Claude sessions, sometimes on other machines, edit these repos concurrently. Before editing, and again right before every `git push`: `git fetch origin -q; git status --porcelain -b`. Confirm you match origin and the tree is clean. Fast-forward if behind; resolve if diverged.
2. **Version bump at check-in.** Any commit that changes real code must, in the same check-in, run `python bump_version.py` and add a matching `CHANGELOG.md` entry, before pushing, without being asked. This was missed twice on epubredactor (2026-09-14, 2026-09-17). `release.ps1` does not bump versions for you.
3. **Progress feedback for every slow operation.** Every slow operation (folder scan, load, probe, conversion, network call, reload) shows a progress dialog: `redactor_common.gui.progress.run_with_progress()` for loops (`cancellable=False` for read-only scans and reloads, `True` for applies that mutate), `run_busy()` for a single long call. The only exception is a live-typing preview (search/replace, rename pattern) whose per-item work is confirmed cheap by a timing check at large N.
4. **Promote to redactor_common first.** A fix or feature useful to more than one app is built and verified in `redactor_common`, version-bumped, tagged, and pushed. Then each app bumps its `requirements.txt` pin plus its own `APP_VERSION` and `CHANGELOG.md`. Flag a stale pin rather than ignoring it.
5. **Landing page honesty.** erlbon.github.io's Formats table must match the app's real menu actions and file-picker filters, not what the underlying library could theoretically do.
6. **Cross-platform goal.** A Linux/Mac port is planned. Avoid new unguarded Windows-only code (registry, hardcoded `C:\` paths, Windows APIs without a `sys.platform` guard). Follow the existing patterns: PATH-based tool lookup (`redactor_common/core/tool_locator.py`), `QSettings` with `IniFormat` and an explicit path, `sys.platform == "win32"` guards.
7. **PowerShell 5.1 pitfall in release scripts.** Under `$ErrorActionPreference = "Stop"`, a native command's stderr becomes a terminating error. Redirect only stdout (`cmd | Out-Null`), never `2>&1`, and reset `$LASTEXITCODE` after reading it. Also, the release script tags and pushes before `gh release create`, so "tag exists, release doesn't" is a resumable state; check with `gh release view <tag>`.

8. **Merge straight to main.** One developer, no reviewer (Erlend, 2026-09-28). Finished work that passes its tests is merged into `main` and pushed, not left waiting on a branch or in a PR. If a PR was opened, merge it once CI is green and delete the branch.

Full text of these rules: `.claude/skills/redactor-conventions/SKILL.md` in redactor_common.

## Machine-local, not in git
The release scripts (`release.ps1`, `release-<project>.ps1`, `release-all.ps1`) and a hand-placed `upx.exe` lived in a machine-local `_shared-tools` folder that is deliberately not in git. They are not in this repo and must be recreated or copied over by hand.

