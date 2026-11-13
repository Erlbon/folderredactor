# Changelog

## 2026-11-13#01 -- One service that is down no longer blocks the rest

- **Look Up asks again.** After two folders in a row could not reach a service, every later Look Up answered "skipped:
  the services could not be reached" for as long as the library stayed open, also when the service was back. The early
  stop now ends with the run it belongs to.
- **A pasted Wikipedia link works while MusicBrainz is down.** For an artist it used to fail on the MusicBrainz id the
  article names; it now builds from Discogs when the article names a Discogs id and the token is set, else a thin draft
  from the article itself, and the reasons say MusicBrainz could not be reached. For an album the failed MusicBrainz
  search no longer ends the lookup before the article (or Discogs) is used.
- Command line: a folder given a `--link` is looked up also after the run stopped early for the other folders.

## 2026-11-10#01 -- One window: the library tree and the note pane

The window review of 2026-11-10 (`docs/ui-review-2026-11-10.md`), as Erlend answered it.

- **No separate notes window any more.** The library is a tree on the left; the note of the selected folder is
  always open on the right. The "which folder?" question, the locked progress window, the review window with its two
  views and the summary boxes are gone.
- **A light on every folder**, told apart by shape as well as colour: ● green a note, ◐ amber a draft waiting (or an
  outdated note of ours), ✎ green a note you edited, ○ hollow grey no note. Letter folders get none. A folder's
  children are listed when it is opened, and the note states are read by a background thread: no walk of the library.
- **Look Up** (Notes > Look Up, Ctrl+L) works on the selected folder: on its own as whatever it is, or with This
  Folder and Below for the kinds ticked under Look Up Options (also: Also Refresh Outdated Notes). It runs in the
  background; each draft lands in the tree as it is ready and can be judged while the rest are looked up. The bottom
  line says how far it is, with Cancel. Music or video is told from the selected folder's files.
- **The note pane** shows the folder's draft, else its note on disk, else "No note"; Preview / Raw / Before-after
  switch at the top (Ctrl+1/2/3) and stay put from folder to folder. For a draft that is not settled the **Match** strip
  opens above the note (candidates: double-click or Enter builds the note; level, link, minimal note from the tags,
  genres); it folds away once the draft can be written.
- **Local files** (cover, albums, tracks, tags) moved under the tree (View > Folder Panel).
- **Writing:** tick boxes in the tree (confident drafts come ticked), one Write N ticked notes button (Ctrl+Enter),
  Enter in the tree writes the selected draft and goes to the next one waiting, F8 goes to the next waiting folder.
  Tick All Confident, Tick Best Guesses and Untick All are in the Notes menu. The "replace an older note?" question
  stays; the summary box went to the status bar.
- **Edit a note in the pane** (Edit, F4): Save writes it while the note on disk is still what was read, the old text to
  the Recycle Bin; it then reads as edited by you and Look Up leaves it alone. Moving away with unsaved changes asks.
- **Edit > Undo** takes back the last note written or saved here (with Tools > History on).
- **The greyed Clean Up menu is gone.** The folder-name check comes back, built, in this window: a naming mark per
  folder in the tree, the fix in the pane, Check Names beside Look Up. Notes > Refresh Old Notes and Switch View went
  with the old window; View > Command Palette no
  longer also says "not built yet".
- Tools > Preferences: the Create Notes groups are called Look Up.

## 2026-11-08#05 -- The first release (v0.1)

- **Release notes of their own** (`docs/releases/v<build>.md`, named in `pyproject.toml`): the release tool takes them
  instead of only this version's CHANGELOG section. The first ones say what the program does as a whole.
- The notes' lookup cache from a run from source (`folderredactor_notes_cache.sqlite`) is ignored by git, like the
  other files beside the program.

## 2026-11-08#04 -- `notes --update` refreshes notes again

- **Fixed:** `folderredactor notes PATH --update` ran the program's own update check ("GitHub lists no published
  release", exit 2) instead of refreshing the old notes, since 2026-11-08#03. The update flags (`--check-update`,
  `--update`) now count only when no command name comes first; after `notes` they are the command's own options.
  The release tool's calls (`--version`, `--check-update`, `--update`, each with `--release-tag` / `--result-file`)
  are answered as before.

## 2026-11-08#03 -- An installer, and updates through the family's update framework

- **A per-user installer**, `folderredactor-setup.exe` (Inno Setup 6, no administrator rights, a Start menu entry),
  around a one-folder build that starts faster than the one-file exe. The one-file `folderredactor.exe` stays the
  portable download. `build_exe.bat` builds both, and the installer, with this repo's `.venv`; no UPX.
- **Updates through the family's update framework** (redactor_common `docs/update-framework.md`): every build says
  how it was put on the PC (the installer writes `windows-installer` beside the program, the one-file exe carries
  `windows-exe`), and Help > Check for Updates installs the file the release's `update-manifest.json` names for that
  channel, after checking its size and checksum; when it cannot, it says why instead of only offering the release
  page. The installer includes the family's installer contract (start again after a silent update, wait for the
  program to let go of its files).
- **`--check-update` and `--update`** on the command line (`--release-tag vX`, `--result-file PATH`): what this copy
  would do with a release, as JSON, or do it with no window. The release tool's gate asks the previous release this.
- `pyproject.toml` holds the release tool's configuration (`python -m redactor_common.release publish`).

## 2026-11-08#02 -- redactor_common 2026-11-08-02

- **redactor_common 2026-11-08-02** (was 2026-11-06-03), the family's one pin: the update framework (an update
  manifest in every release, the declared update channel, the shared installer contract, the release tool and its
  gate) and the update check falling back to GitHub's API when a release download fails. Nothing here uses it yet;
  the next check-in moves this app onto it.

## 2026-11-08#01 -- The notes tell pluteus where the artists are (plan step 11b, D26)

pluteus builds no index of a library: music apps find the artists and albums from the folder notes. Two things more are
written for that.

- **`layout:` in every genre or collection `about.md`**: the levels below the folder down to the album, from the folders
  alone. `0 - Bands` above its letter folders says `letter/artist/album`, a genre above country folders
  `country/artist/album`, a genre of artist folders `artist/album`, a collection of albums (`6.2 - Compilations`) `album`.
  The line sits in the front matter before the stamp, and the stamp covers it.
- **A folder above letter, country or sub-genre folders is a genre level now** and gets its `about.md` (not the folder
  you scan from when that is the library root). `0 - Bands` (a name that is no genre) gets a short `about.md` that only
  says how it is sorted; so does a collection by name (`Compilations`, `Soundtracks`) when Wikipedia has no genre article
  for it. Letter folders still get no note.
- **An `about.md` that is already there without the line** (yours or ours) is offered when "Also review notes made by an
  older version" is ticked (`--update` on the command line): on a yes the one line is added to its front matter, every
  other line kept (`status: draft` and your own keys too); the note as it was goes to the Recycle Bin and History can undo
  it. A note of ours nobody edited still counts as ours afterwards. A note edited between the look and the yes is left alone.
- **Box sets**: a box whose albums sit in disc folders (`Box/Disc 1 - .../[1953] - Album/songs`) is one album. It gets
  one `album.md` in the box folder, which makes pluteus show the whole box as one album under the artist; the disc folders
  and the albums inside them get none (before, each disc folder was taken for an artist). The box is looked up by its own
  title (an `Artist - ` in front dropped), not by the album tags of the albums inside it.

## 2026-11-06#07 -- The Redactors' shared keys (plan step 11a, D25)

- **The API keys are shared by the Redactors**: one entry per service in the credential store
  (`<name>@redactor/shared`) instead of one per program. A key saved in Tools > API Keys is the key for every Redactor
  that uses it, and each row says which others those are. Read: the environment variable, then the shared key, then this
  program's own key from before. Remove takes the key away for all of them (and this program's old copy).
- **The first-start offer now shares** the keys still kept by one program only (mp3redactor's Discogs token,
  videoredactor's TMDB key, or this program's own from before) instead of copying them into this program; the old
  entries stay for the Redactors that do not read the shared keys yet. When this program had its own copy, that one is
  shared, so sharing never changes the key in use here. Never silent; File > Import offers it again.
- **redactor_common 2026-11-06-03** (was 2026-11-06-02): the shared key store (`secret_store.get_key` / `set_key` /
  `unshared_keys` / `share_keys`, the family's key registry, `SecretField(shared=True)`), and the Discogs client reads
  the shared token.

## 2026-11-06#06 -- The full check (plan step 11)

- **Checked on the built exe**: the window starts and opens a library; the command line, run as ABOUT.md says for
  scripts, drafted and wrote the artist and album notes of a real ffmpeg-encoded library (MP3 and FLAC albums, live
  MusicBrainz and Wikipedia), never overwrote them on a second run, refused a music option for video and reported a
  missing TMDB key with exit code 1.
- **Fixed, found by that check**: `notes` with a music folder and a video folder in one call scanned the video folder as
  music and said nothing; PATHs that hold music and video are now refused with a message (run them separately, or say
  `--media`).
- **`build_exe.bat` builds with this repo's own `.venv`** (made at the redactor_common pin by `venv_sync.py`) instead of
  installing the requirements into the shared Python, which breaks the other repos' pins. README's commands say the same.
- ABOUT.md: how to draft old notes again (the folder question's "Also review notes made by an older version"), and the
  one-kind-per-run rule of `--media`.

## 2026-11-06#05 -- One `notes` command for music and video, the old apps' settings and keys (plan step 10)

- **`notes` does music too**: one command for both, as mp3redactor's and videoredactor's were. `--media auto` (the
  default) tells them apart by the file names; a real mix asks for `--media music` or `--media video`, and a folder
  without any media file goes by the `--kind` words. Music has mp3redactor's options (`--link`, `--genres`, `--discogs`,
  `--no-discogs`, `--no-singles`, `--norwegian-numbers`); they are refused for video. Checked live on real encoded files:
  the same result as mp3redactor's own command.
- **Music's engine options are settings** (`[notes.music]`) with switches in Tools > Preferences: ask Discogs for every
  artist, leave the singles out, Norwegian number words. The window and the command line both follow them (a flag wins
  for one run).
- **Opening a library says what kind it is** ("a music library", "a video library"), and Notes > Create Notes uses that.
- **File > Import from mp3redactor or videoredactor…**: their Create Notes settings and saved lookup answers, from the
  folder the old program is in, filling only what is not set here; and their API keys. At the first start the keys are
  offered once (never copied without a yes).
- Tests: mp3redactor's command-line notes tests moved (its own test file and the command-line tests of nine others),
  plus tests of the media choice and the import. A test that renamed a folder of freshly written files (Windows can hold
  such a folder for a moment) now makes its folders under their final names.

## 2026-11-06#04 -- Music notes in the window, on mp3redactor's review page (plan step 9)

- **Notes > Create Notes works for music libraries**: artist, album and genre / collection notes, with mp3redactor's
  "What to create" choices (artist notes only at first). The window works out from the library's file names whether it
  is music or video (when it cannot tell: the kind used last time, else it asks).
- **The review page is mp3redactor's**, now redactor_common's shared page (Erlend, 2026-11-06: the template for every
  media type). Video gets it too: the list never jumps after a pick (rows update in place, the scroll position stays), a
  line under the list says why a row cannot be ticked, notes from the first versions are flagged, and a candidate that
  cannot be used says why.
- **Music's extras on that page**: Build this folder as (artist, album, genre / collection, skip), Look up by link
  (checked before anything is fetched), Create a minimal note from the tags, Genres covered, the Local files tab
  (cover, tracks and tags as the files carry them), Tick best guesses, and "Create the album notes for these artists too"
  after artist notes.
- **Tools > Preferences**: "Log the review list for troubleshooting" (off by default) with a Delete Log button.
- **redactor_common 2026-11-06-02** (was 2026-11-06-01), the release that made mp3redactor's page the shared one.
- Tests: the music window-flow scenarios of mp3redactor, rewritten for this window (it opens a library folder instead of
  loading files into a table), and the Local files view's own tests; one driving helper for the music and video
  window-flow tests.

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
