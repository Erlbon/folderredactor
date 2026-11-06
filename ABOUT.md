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
for music libraries (artists, albums, genres, moved here from the ɯP3 Redactor) and video libraries (series and films,
from the Ʌideo Redactor) in the window; on the command line `notes` does video only so far. The Clean Up menu is shown
greyed until it is built.

## Opening a library

File > Open Library Folder (Ctrl+Shift+O), File > Recent, a folder dropped on the window, or a folder on the command
line (`folderredactor.exe D:\Music`).

## Folder notes

Notes > Create Notes works out from the file names of the library you opened whether it is a music or a video library
(when it cannot tell, it takes the kind you used last time, and the first time it asks). Then it asks which folder: the
library you opened, the folder you used last time, or another one, and which notes to make.

The review page is the same for both: one note at a time for a single folder (or one artist with its albums), a list
with ticks for several. The list never jumps when you pick something: the row is built again where it is. Under the
list a line says why a row cannot be ticked yet. Only what you say yes to is written, with `status: draft` in the note,
and a folder that already has a note (`artist.md`, `author.md`, `series.md`, `album.md` or `about.md`, any letter case)
is never touched.

### Music

An artist folder (album folders below it) gets an `artist.md`, an album folder (music files in it, or in CD1 / Disc 2
folders) an `album.md`, a genre or collection folder (artist folders below it; `Various Artists`, `Soundtracks`; a
folder whose name starts with `_`) an `about.md`. MP3, FLAC, M4A, Ogg and Opus files all count. Artist notes only are
ticked at first ("What to create"); album notes are slower (about four requests each). After artist notes are written
the page offers the album notes of those artists with one click.

Each folder is looked up at MusicBrainz and Wikipedia, and at Discogs when you saved a Discogs token. A match is
*confident* only when the albums in your folder are in that artist's discography and no other artist fits as well; two
bands with one name, or a "Greatest Hits" anyone could have, stay uncertain. For an uncertain folder the page offers:
the candidates found (with how many of your albums each holds), **Build this folder as** (artist, album, genre or
collection, or skip it), **Look up by link** (paste the right MusicBrainz, Discogs, Wikipedia or Wikidata page; nothing
is fetched from any other site), **Create a minimal note from the tags** (no online source, and it says so), and the
**Local files** tab: the cover, the track list and the tags as the files carry them. **Tick best guesses** in the list
ticks the uncertain folders whose top candidate holds one of your albums (still drafts, still only written on a click).
A genre folder has a **Genres covered** box: edit it and look it up again.

The notes the ɯP3 Redactor already wrote count as this program's own: they are not offered again.

### Video

A series folder (episodes named `S01E02`, directly in it or in Season folders) gets a
`series.md`; a film folder (one film, perhaps with a part 2 or a trailer) gets an `about.md`. A folder of many loose
films, or one called `Movies` or `Downloads`, gets no note and its subfolders are looked at instead.

Each folder is looked up at TMDB (your own key, see API keys below). A match is *confident* only when TMDB has exactly
one title with the folder's name (and year), and for a series the seasons and episode numbers in the folder fit it;
when several series share a name, the air dates in the file names or the exact episode counts can still tell them
apart. The introduction comes from Wikipedia only when Wikidata links the article to the title's IMDb id, never from a
guess by name. Uncertain folders show their candidates for you to pick.

The notes the Ʌideo Redactor already wrote count as this program's own: they are not offered again.

### Preferences

Tools > Preferences > Create Notes switches the lookup cache (answers kept next to the program, so a second run is
quick) and the Wikipedia introduction; Tools > Clear Lookup Cache forgets the saved answers. "Log the review list for
troubleshooting" is off by default: it writes only counts, scroll positions and folder names next to the program, and
Delete Log removes it.

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
