# The Ⅎolder Redactor

A tool for the folders of a media library, not for the files in them. It has two jobs:

1. **Folder notes.** It drafts the short Markdown notes that the Pluteus media server shows for a folder
   (`artist.md`, `album.md`, `series.md`, `about.md`), from the files' own tags and names and from MusicBrainz,
   Discogs, TMDB and Wikipedia. You review every draft and say yes or no; only a yes is written.
2. **Folder-tree clean-up.** It checks a library's folder tree against that library's conventions (stray spaces,
   release tags, year forms, numbering ...) and proposes renames. Again you say yes or no, and every rename can be
   undone.

What it writes into a library: `.md` files that explain a folder's contents, and nothing else. Its settings, caches,
reports and history live next to the program.

Part of the Redactor family (the ƎPUB, ɯP3, Ʌideo and ƆBZ Redactors). This is an early build: the window, the
menus, the API Keys, History and Preferences dialogs are in place; the Notes and Clean Up menus are shown greyed
until their parts are built.

## Opening a library

File > Open Library Folder (Ctrl+Shift+O), File > Recent, a folder dropped on the window, or a folder on the command
line (`folderredactor.exe D:\Music`).

## API keys

Tools > API Keys holds a Discogs token (music) and a TMDB API key (films and series). Both are free to get and are
kept in your system's credential store, never in a settings file. MusicBrainz and Wikipedia need no key. The
environment variables `DISCOGS_TOKEN` and `TMDB_API_KEY` win over what is stored.

## History

Tools > History lists what the program wrote, with an undo for each. It is off until you turn it on (Tools >
Preferences, or the question Tools > History asks the first time), and Preferences has a button that deletes what
was recorded.

## Command line

The one exe (`folderredactor.exe`, or `python main.py` from source) is also the command line. When its first
argument is a command name, it runs that command and the window never opens; with no command, or with a folder to
open, the window starts as usual. `folderredactor --help` lists the commands and `folderredactor COMMAND --help`
lists the options of one.

There are no commands yet. They come with the two jobs: `notes` (draft the folder notes; a dry run unless
`--write`), and `check`, `apply` and `undo` (the folder-tree clean-up). Every command will take `--json` (one JSON
document on stdout), `--quiet` and `--output FILE`, and the ones that change something will be a dry run unless
`--write`.

| Option | Meaning |
| --- | --- |
| `-h`, `--help` | Help for the program or for one command. |
| `--version` | The version (top level only). |

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Done. |
| 1 | The command ran but some items failed or have problems. |
| 2 | Bad arguments. The reason is on stderr. |
| 70 | An internal error (a bug); the traceback is on stderr. |
| 130 | Interrupted with Ctrl+C. |

### Using it from scripts and scheduled tasks (Windows)

`folderredactor.exe` is a windowed program: an interactive shell does not wait for it, and a script cannot read its
output unless it is redirected. So for automation ask for the result in a file with `--output`, wait for the
process, and read the exit code: in a batch file cmd waits by itself, in an interactive cmd use `start /wait`, and
in PowerShell `Start-Process folderredactor.exe -ArgumentList ... -Wait -PassThru` (then `.ExitCode`), or pipe it
to `Out-Null` to make PowerShell wait.
