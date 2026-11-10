# The Ⅎolder Redactor

A tool for the folders of a media library, not for the files in them. It drafts the short Markdown notes that the
Pluteus media server shows for a folder (`artist.md`, `album.md`, `series.md`, `about.md`), from the files' own tags and
names and from MusicBrainz, Discogs, TMDB and Wikipedia. You judge every draft; only what you say yes to is written.

What it writes into a library: `.md` files that explain a folder's contents, and nothing else. Its settings, caches and
history live next to the program.

Part of the Redactor family (the ƎPUB, ɯP3, Ʌideo and ƆBZ Redactors). This is an early build: folder notes work for
music libraries (artists, albums, genres, moved here from the ɯP3 Redactor) and video libraries (series and films, from
the Ʌideo Redactor), in the window and with the `notes` command.

## Installing and updating

Two downloads, the same program: `folderredactor-setup.exe` installs it for you alone (no administrator rights, in
your own programs folder, with a Start menu entry), and `folderredactor.exe` is one file to run from anywhere. Help >
Check for Updates (or the once-a-day check, switched on in Tools > Preferences) installs a new version the way your
copy came: the installed copy runs the new installer and starts again, the one file replaces itself. When it cannot,
it says why and offers the release page. Settings, History and the crash log stay beside the program, so an update
keeps them; uninstalling leaves them in the program folder too.

## The window

On the left, the library's folders as a tree; on the right, the note of the folder you select, always open. A folder's
children are listed when you open it, nothing more is read in the background, so a big library on a share opens at once.

Each folder has a light, told apart by its shape as well as its colour:

- ● green: the folder has a note (also one this program did not make: Pluteus shows it all the same)
- ◐ amber: a draft is waiting for you, or the note was made by an older version and can be drafted again
- ✎ green: a note you edited (here or in Pluteus); a lookup never touches it
- ○ hollow grey: no note

Letter folders (`H`, `A-C`, `0-9`) have no light: they never get a note. Under the tree, the **Local files** of the
selected folder: the cover, the albums, the track list and the tags as the files carry them (music; View > Folder Panel
hides it).

The note pane shows the folder's draft if it has one, else the note in the folder, else "No note". Preview, Raw and
Before / after (the old note against the new draft, when a draft replaces a note) switch at the top (Ctrl+1, 2, 3).

## Opening a library

File > Open Library Folder (Ctrl+Shift+O), File > Recent, a folder dropped on the window, or a folder on the command
line (`folderredactor.exe D:\Music`).

## Folder notes

Select a folder and click **Look Up** (Notes > Look Up, Ctrl+L). What it looks up is set under Notes > Look Up Options:
**This Folder and Below** looks at the folders under the selected one too, for the kinds of note ticked there (artists,
albums, genres and collections; series, films); off, only the selected folder is looked up, as whatever it is. Look Up
works out from the file names whether the folder holds music or video (when it cannot tell, it takes the library's
kind or the kind you used last time, and the first time it asks).

The lookup runs in the background: each folder's light turns amber as its draft arrives, and you can read and judge the
first drafts while the rest are looked up. The line at the bottom says how far it is; Cancel stops after the folder in
hand and keeps the drafts so far. F8 (Notes > Next Waiting Folder) goes to the next amber folder.

A confident draft gets a tick box, ticked. **Write N ticked notes** (Ctrl+Enter) writes the ticked ones; Enter in the
tree writes the selected folder's draft and moves to the next one waiting. Notes are written with `status: draft` in
them, and a folder that already has a note (`artist.md`, `author.md`, `series.md`, `album.md` or `about.md`, any letter
case) is never touched. Edit > Undo takes back the last note written, when Tools > History is on.

A note this program (or the ɯP3 or Ʌideo Redactor) wrote in an older shape can be drafted again: tick **Also Refresh
Outdated Notes** under Look Up Options. Such a draft shows Before / after, is never ticked by itself, and the old note
goes to the Recycle Bin when you write the new one. A note you edited is never offered.

**Editing a note.** A note in a folder can be edited in the pane: Edit (F4), change the Raw text, Save. The old text goes
to the Recycle Bin (on a network share without one the save is refused and the note stays as it was). From then on the
note reads as edited by you, and Look Up leaves it alone.

**When a draft is not settled** (uncertain, or nothing found), the **Match** strip opens above the note: the candidates
found (double-click the right one, or select it and press Enter, to build the note from it) and the other ways to settle
it, listed below for music. Once the draft can be written the strip folds away; click Match to open it again.

### Music

An artist folder (album folders below it) gets an `artist.md`, an album folder (music files in it, or in CD1 / Disc 2
folders) an `album.md`, a genre or collection folder (artist folders below it; `Various Artists`, `Soundtracks`; a
folder whose name starts with `_`) an `about.md`. MP3, FLAC, M4A, Ogg and Opus files all count. Artist notes only are
ticked at first (Look Up Options); album notes are slower (about four requests each). For the albums of artists you just
wrote, select the artist and Look Up with Albums ticked.

Each folder is looked up at MusicBrainz and Wikipedia, and at Discogs when you saved a Discogs token. A match is
*confident* only when the albums in your folder are in that artist's discography and no other artist fits as well; two
bands with one name, or a "Greatest Hits" anyone could have, stay uncertain. For an uncertain folder the Match strip offers:
the candidates found (with how many of your albums each holds), **Build this folder as** (artist, album, genre or
collection, or skip it), **Look up by link** (paste the right MusicBrainz, Discogs, Wikipedia or Wikidata page; nothing
is fetched from any other site), and **Create a minimal note from the tags** (no online source, and it says so); the
Local files under the tree show what the folder holds. **Notes > Tick Best Guesses** ticks the uncertain folders whose
top candidate holds one of your albums (still drafts, still only written on a click).
A genre folder has a **Genres covered** box: edit it and look it up again.

**Where pluteus finds the artists.** Every `about.md` this program writes says in its front matter how the folders below
it are arranged, down to the album: `layout: letter/artist/album` above letter folders (`0 - Bands/H/Hellbillies`),
`country/artist/album` above country folders, `artist/album` above artist folders, `album` for a collection whose albums
sit directly inside it (`6.2 - Compilations`). pluteus reads that line instead of opening every folder. A folder above
the artists with a plain name such as `0 - Bands` (no genre to look up) gets a short `about.md` that says only that.
Letter folders (`H`, `A-C`) still get no note. An `about.md` that is already there without the line, yours or ours, is
offered with **Also Refresh Outdated Notes** ticked: on your yes the one line is added to its front
matter, every other line kept (the note as it was goes to the Recycle Bin).

**Box sets.** A box whose albums sit in disc folders (`Tom Lehrer/The Remains of Tom Lehrer/Disc 1 - .../[1953] - Songs
by Tom Lehrer/`) is one album: it gets one `album.md` in the box folder, which is what makes pluteus show the whole box
as one album under the artist. The disc folders and the albums inside them get none.

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

Tools > Preferences > Look Up switches the lookup cache (answers kept next to the program, so a second run is
quick) and the Wikipedia introduction; Tools > Clear Lookup Cache forgets the saved answers. For music: ask Discogs for
every artist (slower; off: only when MusicBrainz has no verified match), leave the singles out of a discography, and
count the Norwegian number words that are everyday English words (en, to, tre, fire...) as numbers. "Log the review list for
troubleshooting" is off by default: it writes only counts, scroll positions and folder names next to the program, and
Delete Log removes it.

## Coming from the ɯP3 or Ʌideo Redactor

At its first start the program offers to share the Discogs token of the ɯP3 Redactor and the TMDB key of the Ʌideo
Redactor with all the Redactors (see API keys below), if they are still saved in that one program only (they stay
there too). File > Import from mp3redactor or videoredactor… offers that again, and also takes over their notes
settings (what to create, the Discogs and singles
switches, the lookup cache and Wikipedia switches) and their saved lookup answers: point it at the folder the old
program is in. It only fills in what is not set here; your choices in this program are never overwritten.

## API keys

Tools > API Keys holds a Discogs token (music) and a TMDB API key (films and series). Both are free to get and are
kept in your system's credential store, never in a settings file. MusicBrainz and Wikipedia need no key. The
environment variables `DISCOGS_TOKEN` and `TMDB_API_KEY` win over what is stored.

The keys are shared by the Redactors: one entry per service in the credential store, so a key saved here is the key
for every Redactor that uses it, and each row says which other Redactors those are (the Discogs token: the ɯP3
Redactor; the TMDB key: the Ʌideo Redactor). The other Redactors read the shared keys from their next version on;
until then they keep their own copy, which is never removed by sharing. Remove takes the key away for all of them.

## History

Tools > History lists what the program wrote, with an undo for each. It is off until you turn it on (Tools >
Preferences, or the question Tools > History asks the first time), and Preferences has a button that deletes what
was recorded.

## Command line

The one exe (`folderredactor.exe`, or `python main.py` from source) is also the command line. When its first
argument is a command name, it runs that command and the window never opens; with no command, or with a folder to
open, the window starts as usual. `folderredactor --help` lists the commands and `folderredactor COMMAND --help`
lists the options of one.

The commands so far: `notes` (draft the folder notes of a music or video library; a report unless `--write`). Every
command takes `--json` (one JSON document on stdout), `--quiet`
and `--output FILE`, and the ones that change something are a report or dry run unless `--write`.

| Option | Meaning |
| --- | --- |
| `-h`, `--help` | Help for the program or for one command. |
| `--version` | The version (top level only). |
| `--check-update [--release-tag vX]` | What this copy would do with the newest release (or release `vX`), as JSON: its update channel, the release, `install`, `page` or `none`, the file and the reason. Downloads and changes nothing. |
| `--update [--release-tag vX]` | The update itself, with no window: download, check, install. |
| `--result-file PATH` | With `--check-update`, `--update` or `--version`: also write the answer to PATH (the exe is a windowed program, so a script may not see its output). |

### notes

`folderredactor notes PATH... [--media MEDIA] [-R] [--kind KIND] [--update] [--update-legacy] [--link FOLDER=URL] [--genres FOLDER=GENRE,GENRE] [--no-cache] [--no-wikipedia] [--write] [--include-uncertain] [-n] [--discogs WHEN] [--no-discogs] [--no-singles] [--norwegian-numbers] [--show-drafts]`

Drafts the Markdown notes the Pluteus media server shows beside a folder, the same as Notes > Look Up. **Music:**
`artist.md` in an artist folder, `album.md` in an album folder, `about.md` in a genre or collection folder, from
MusicBrainz, Wikipedia and (with your Discogs token under Tools > API Keys, or `DISCOGS_TOKEN`) Discogs, verified by the
albums really in the folder. **Video:** `series.md` in a series folder and `about.md` in a film folder, from TMDB (your
own key under Tools > API Keys, or `TMDB_API_KEY`) and, when Wikidata links the title's IMDb id to an article, a
Wikipedia introduction. A report unless `--write` is given: every folder is listed with how sure the match is and what
would be written. `--write` writes the drafts (`status: draft`) of the confident matches only. A folder that already has
a note (any of Pluteus's names, any letter case) is never touched, and a note is never overwritten. Uncertain and
unmatched folders are listed with the reasons and the candidates and not written.

| Option | Meaning |
| --- | --- |
| `--media MEDIA` | `music`, `video` or `auto` (the default): tells them apart by the file names in each PATH. One run is one kind: PATHs that hold music and video are refused (run them separately), and a folder too mixed to tell asks for `--media`. |
| `-R`, `--no-recurse` | Look only at the folders named, not the folders below them. |
| `--kind KIND` | Which notes. Music: `artist` (the default: fast, no album lookups), `album`, `genre` (`about.md` of a genre or collection folder: about one Wikipedia lookup each, no tags read), `both` (artist and album), `all`, or several joined by commas (`artist,genre`). Video: `series`, `movie` or `both` (the default). |
| `--link FOLDER=URL` | Music: the right page for a folder the search does not find, e.g. `--link "Leningrad=https://en.wikipedia.org/wiki/Leningrad_(band)"` (FOLDER is its name or path; URL a Wikipedia, MusicBrainz, Discogs or Wikidata link, or a MusicBrainz id). Repeatable. |
| `--genres FOLDER=GENRE,GENRE` | Music: the genres a genre or collection folder covers when its name does not say so, e.g. `--genres "1.61 - Ska=Ska,Ska punk"`. Each is checked on Wikipedia. Repeatable. |
| `--discogs WHEN` | Music, with a Discogs token: `fallback` (only when MusicBrainz has no verified match or Wikipedia no introduction), `always` (every artist, slower) or `never`. The default follows Tools > Preferences. |
| `--no-discogs` | Music: do not use Discogs even with a token (= `--discogs never`). |
| `--no-singles` | Music: leave the singles out of an artist's discography (faster). Also on when Preferences says so. |
| `--norwegian-numbers` | Music: also read the Norwegian number words that are everyday English words (en, to, tre, fire, fem, ni, ti) as numbers when titles are compared. Also on when Preferences says so. |
| `--update` | Also list the notes made by an older version of this program (stamped, an older format, nobody edited them) and, with `--write`, replace only those; the old note goes to the Recycle Bin. A note a person edited, or one this program did not write, is never replaced; the one change made to it (music, `--kind genre`) is the `layout:` line added to an `about.md` that lacks it, every other line kept. On a network share without a Recycle Bin the old note is kept and the replace is reported as failed. |
| `--update-legacy` | With `--update --write`: also replace the notes of the first versions (no stamp, so it cannot be known whether they were edited; still the Recycle Bin, still never an edited or foreign note). |
| `--no-cache` | Do not use the disk cache of earlier answers: everything is asked again. |
| `--no-wikipedia` | No Wikipedia introduction in the notes (fewer requests). |
| `--write` | Write the drafts of the confident matches (the default is a report only). |
| `--include-uncertain` | With `--write`: also write an uncertain match from the engine's best candidate (music: one that holds one of your albums; video: one that fits the name and year on its own and has no equal), never for nothing found or an unclear level; marked "from an uncertain match" in the report. |
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
