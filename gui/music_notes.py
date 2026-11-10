"""
gui/music_notes.py

What the window needs to know about music notes (core/music/flow.py is the engine): the kinds Look Up can be told to make,
the music extras of the review controls (redactor_common's ReviewHooks: the level choice, the minimal note from the tags,
Look up by link, the genres a genre folder covers, why a candidate cannot be used, best guesses, the opt-in troubleshooting
log), the words when there is nothing to look up, and the engine as the window's lookup thread makes it. The window is
gui/main_window.py; the Local files panel under the tree is gui/music_evidence_view.py.

  KIND_CHECKS                       (kind, Look Up menu label), mp3redactor's order
  music_hooks(engine)               the review controls' music extras (`engine` may be a stand-in that finds the engine late)
  nothing_found_why(found)          the music words when a Look Up finds nothing to look up
  make_engine(fetchers, cache)      the engine of one library, with the options of Preferences
"""

from __future__ import annotations

from typing import Optional

from core import notes_debug, notes_settings
from core.music.flow import LEVEL_LOCAL_TAGS, Fetchers, NotesEngine, Proposal
from core.music.level import SUGGEST_ALBUM, SUGGEST_ARTIST, SUGGEST_COLLECTION, SUGGEST_SKIP
from core.music.link import LinkError, parse_link
from core.music.local import KIND_ALBUM, KIND_ARTIST, KIND_GENRE, LIBRARY_ROOT_MESSAGE
from redactor_common.gui.notes_review_dialog import ReviewHooks

KIND_CHECKS = (  # mp3redactor's order; the words are Notes > Look Up Options entries
    (KIND_GENRE, "&Genres and Collections (fast: about one Wikipedia lookup each)"),
    (KIND_ARTIST, "&Artists (about 5 requests each)"),
    (KIND_ALBUM, "A&lbums (slower: about 4 requests each)"),
)
CANDIDATE_COLUMNS = ("Name", "Details (year, country)", "Score", "Source", "Local albums found")
DISCOGS_NOTE = "Discogs token not set: notes will be thinner (Tools > API Keys…)."
LEVEL_LABELS = {
    SUGGEST_ARTIST: "Artist folder (artist.md)",
    SUGGEST_COLLECTION: "Genre or collection (about.md)",
    SUGGEST_ALBUM: "Album folder (album.md)",
    SUGGEST_SKIP: "Skip this folder",
}
_CURRENT_LEVEL_KEY = {"collection": SUGGEST_COLLECTION, "genre": SUGGEST_COLLECTION, "artist": SUGGEST_ARTIST,
                      "album": SUGGEST_ALBUM}
LOCAL_LABEL = "Create a minimal note from the tags"
LOCAL_TOOLTIP = ("Title, year and tracklist read from the files (an artist: the album folder names), written as a draft that "
                 "says it has no online source. Nothing is looked up.")
LINK_PLACEHOLDER = "Paste a Wikipedia, MusicBrainz or Discogs link (or a MusicBrainz id)"
GENRE_LINK_PLACEHOLDER = "Paste the Wikipedia article about the genre"
GENRE_LINK_ONLY = ("For a genre or collection folder paste the Wikipedia article about the genre "
                   "(a link like https://en.wikipedia.org/wiki/Ska_punk).")
RECYCLE_NOTE = ("The old note goes to the Recycle Bin. You can restore it from the Recycle Bin. On a network drive there is "
                "no Recycle Bin: the update is refused and the old note stays.")


# ---- the review page's music extras -------------------------------------------------------------------------------------

def _is_genre_row(p: Proposal) -> bool:
    return p.note_kind == "about"


def _link_placeholder(p: Proposal) -> str:
    if _is_genre_row(p):
        return GENRE_LINK_PLACEHOLDER
    return LINK_PLACEHOLDER if p.kind in (KIND_ARTIST, KIND_ALBUM) else ""


def check_link(p: Proposal, text: str) -> str:
    """'' for a link the engine can use for this row, else the plain message (nothing is fetched to check it)."""
    try:
        target = parse_link(text, bare_as="release-group" if p.kind == KIND_ALBUM else "artist")
        if _is_genre_row(p) and target.kind != "wikipedia":
            raise LinkError(GENRE_LINK_ONLY)
    except LinkError as exc:
        return str(exc)
    return ""


def _genres_of(p: Proposal) -> Optional[list[str]]:
    if not _is_genre_row(p):
        return None
    return list(p.genres) if getattr(p, "genres", None) else [p.title or p.folder.name]


def _log(step: str, **fields) -> None:
    notes_debug.record(step, **fields)  # nothing happens while the log is off


def music_hooks(engine) -> ReviewHooks:
    """The music extras of the review controls. The Local files view is not among them: it sits under the tree."""
    return ReviewHooks(
        level_labels=LEVEL_LABELS, current_level_key=lambda p: _CURRENT_LEVEL_KEY.get(getattr(p, "level", ""), ""),
        skip_level=SUGGEST_SKIP, local_level=LEVEL_LOCAL_TAGS, local_label=LOCAL_LABEL, local_tooltip=LOCAL_TOOLTIP,
        can_make_local=lambda p: p.kind in (KIND_ARTIST, KIND_ALBUM) and p.note_kind in ("artist", "album"),
        link_placeholder=_link_placeholder, check_link=check_link, link_errors=(LinkError,), genres_of=_genres_of,
        best_guess=lambda p: engine.best_guess(p), why_not=lambda p, c: engine.why_cannot_choose(p, c),
        log=_log if notes_debug.enabled() else None, recycle_note=RECYCLE_NOTE)


# ---- the engine --------------------------------------------------------------------------------------------------------

def nothing_found_why(found) -> str:
    """The music words when a Look Up finds nothing to look up: a level that was not asked for, a library root ('' = the
    usual words)."""
    wrong = found.wrong_level_message("tick it under Notes > Look Up Options")
    if wrong:  # an album folder asked for artist notes only: say so, it is not a library root
        return wrong
    return LIBRARY_ROOT_MESSAGE if found.only_a_library_root else ""


def make_engine(fetchers: Fetchers, cache=None) -> NotesEngine:
    """The engine of one library, with the options of Preferences (core/music/settings.py)."""
    from core.music import settings as music_settings

    options = music_settings.engine_options()
    music_settings.apply_number_words()
    fetchers.wikipedia = fetchers.wikipedia and notes_settings.wikipedia_enabled()
    return NotesEngine(fetchers, cache=cache, discogs_mode=options["discogs_mode"], singles=options["singles"])
