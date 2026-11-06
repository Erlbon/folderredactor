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

Part of the Redactor family (the ƎPUB, ɯP3, Ʌideo and ƆBZ Redactors). This is an early build: folder notes work
for video libraries (series and films, moved here from the Ʌideo Redactor); music notes and the Clean Up menu are
shown greyed until their parts are built.

## Opening a library

File > Open Library Folder (Ctrl+Shift+O), File > Recent, a folder dropped on the window, or a folder on the command
line (`folderredactor.exe D:\Music`).

## Folder notes (video)

Notes > Create Notes first asks which folder: the library you opened, the folder you used last time, or another one,
and which notes to make. A series folder (episodes named `S01E02`, directly in it or in Season folders) gets a
`series.md`; a film folder (one film, perhaps with a part 2 or a trailer) gets an `about.md`. A folder of many loose
films, or one called `Movies` or `Downloads`, gets no note and its subfolders are looked at instead.

Each folder is looked up at TMDB (your own key, see API keys below). A match is *confident* only when TMDB has exactly
one title with the folder's name (and year), and for a series the seasons and episode numbers in the folder fit it;
when several series share a name, the air dates in the file names or the exact episode counts can still tell them
apart. The introduction comes from Wikipedia only when Wikidata links the article to the title's IMDb id, never from a
guess by name. Then the review page opens: one note at a time for a single folder, a list with ticks for several.
Uncertain folders show their candidates for you to pick. Only what you say yes to is written, with `status: draft`
in the note. A folder that already has a note (`artist.md`, `author.md`, `series.md`, `album.md` or `about.md`, any
letter case) is never touched.

The notes the Ʌideo Redactor already wrote count as this program's own: they are not offered again.

Tools > Preferences > Create Notes switches the lookup cache (answers kept next to the program, so a second run is
quick) and the Wikipedia introduction; Tools > Clear Lookup Cache forgets the saved answers.

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

The commands so far: `notes` (draft the folder notes of a video library; a report unless `--write`). The clean-up's
`check`, `apply` and `undo` come with that job. Every command takes `--json` (one JSON document on stdout), `--quiet`
and `--output FILE`, and the ones that change something are a report or dry run unless `--write`.

| Option | Meaning |
| --- | --- |
| `-h`, `--help` | Help for the program or for one command. |
| `--version` | The version (top level only). |

### notes

`folderredactor notes PATH... [-R] [--kind KIND] [--update] [--update-legacy] [--no-cache] [--no-wikipedia] [--write] [--include-uncertain] [-n] [--show-drafts]`

Drafts the Markdown notes the Pluteus media server shows beside a folder, the same as Notes > Create Notes: `series.md`
in a series folder and `about.md` in a film folder, from TMDB (your own key under Tools > API Keys, or `TMDB_API_KEY`)
and, when Wikidata links the title's IMDb id to an article, a Wikipedia introduction. Video libraries for now; music
joins this same command later, with the same options. A report unless `--write` is given: every title folder is listed
with how sure the match is and what would be written. `--write` writes the drafts (`status: draft`) of the confident
matches only. A folder that already has a note (any of Pluteus's names, any letter case) is never touched, and a note
is never overwritten. Uncertain and unmatched folders are listed with the reasons and the candidates and not written.

| Option | Meaning |
| --- | --- |
| `-R`, `--no-recurse` | Look only at the folders named, not the folders below them. |
| `--kind KIND` | Which notes: `series` (`series.md`), `movie` (`about.md` of a film folder) or `both` (the default); several can be joined by commas. |
| `--update` | Also list the notes made by an older version of this program (stamped, an older format, nobody edited them) and, with `--write`, replace only those; the old note goes to the Recycle Bin. A note a person edited, or one this program did not write, is never touched. On a network share without a Recycle Bin the old note is kept and the replace is reported as failed. |
| `--update-legacy` | With `--update --write`: also replace the notes of the first versions (no stamp, so it cannot be known whether they were edited; still the Recycle Bin, still never an edited or foreign note). |
| `--no-cache` | Do not use the disk cache of earlier answers: everything is asked again. |
| `--no-wikipedia` | No Wikipedia introduction in the notes (fewer requests). |
| `--write` | Write the drafts of the confident matches (the default is a report only). |
| `--include-uncertain` | With `--write`: also write an uncertain match whose top candidate fits the name and year on its own and has no equal; marked "from an uncertain match" in the report. |
| `-n`, `--dry-run` | Never write, even with `--write`: show what would be written. |
| `--show-drafts` | Print each draft note (text) or include it (`--json`). |

Exit code 1 if a lookup failed (no key, no network); uncertain folders are not failures.

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
