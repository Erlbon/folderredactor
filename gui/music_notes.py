"""
gui/music_notes.py

Notes > Create Notes... for a music library: the questions and the run (core/music/flow.py is the engine). The question
"which folder, and what to create?" is redactor_common's NotesScopeDialog, the progress and the review page are
redactor_common's run_create_notes / NotesReviewDialog, whose template is mp3redactor's page; this module says what is
music's own (plan step 9): the kinds (artist, album, genre / collection), what a folder would get, the time hint, and the
page's music extras as ReviewHooks: the level choice, the minimal note from the tags, Look up by link, the genres a genre
folder covers, the Local files tab, Tick best guesses, 'Create the album notes for these artists too' and the opt-in
troubleshooting log.

  scope_question(parent, ...)       the 'which folder?' dialog with the music words; returns (folder, kinds, outdated)
  create_notes(parent, paths, ...)  scan, look up (progress + Cancel), open the review page; runs the album follow-up
  music_hooks(engine, kinds)        the review page's music extras
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget

from core import notes_debug, notes_settings
from core.music import scope as music_scope
from core.music.flow import (
    LEVEL_LOCAL_TAGS, Candidate, Fetchers, NotesEngine, Proposal, build_proposals, live_fetchers, scan, write_proposal,
)
from core.music.kinds import kinds_text, parse_kinds
from core.music.level import SUGGEST_ALBUM, SUGGEST_ARTIST, SUGGEST_COLLECTION, SUGGEST_SKIP
from core.music.link import LinkError, parse_link
from core.music.local import ALL_KINDS, KIND_ALBUM, KIND_ARTIST, KIND_GENRE, LIBRARY_ROOT_MESSAGE
from redactor_common.core.notes_scope import ScopeChoice
from redactor_common.gui.notes_review_dialog import NotesReviewDialog, ReviewHooks, open_in_system
from redactor_common.gui.notes_run import run_create_notes
from redactor_common.gui.notes_scope_dialog import ask_scope

TITLE = "Create Notes"
KIND_CHECKS = (  # mp3redactor's words and order
    (KIND_GENRE, "Genre / collection notes (fast: about one Wikipedia lookup per folder, no tags read)"),
    (KIND_ARTIST, "Artist notes (about 5 requests each)"),
    (KIND_ALBUM, "Album notes (slower: about 4 requests each)"),
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
FOLLOWUP_LABEL = "Create the album notes for these artists too"
FOLLOWUP_TOOLTIP = "Closes this page and looks up only the albums of the artists whose notes were just written."


# ---- the question -----------------------------------------------------------------------------------------------------

def scope_question(
    parent: QWidget, choices: list[ScopeChoice], include_subfolders: bool,
    on_include_changed: Optional[Callable[[bool], None]] = None, start: str = "", kinds: str = "",
) -> tuple[str, str, bool]:
    """(folder, kinds, include_outdated); folder is "" when the person cancelled."""
    return ask_scope(
        parent, choices, include_subfolders, kind_checks=KIND_CHECKS, kinds=kinds or kinds_text(ALL_KINDS[:1]),
        parse_kinds=parse_kinds, kinds_text=kinds_text, describe=music_scope.folder_info,
        caption_of=music_scope.folder_caption, count=music_scope.count_targets, hint=music_scope.scope_hint,
        on_include_changed=on_include_changed, start=start,
        title="Create Notes: which folder?", heading="Create notes: which folder?",
        browse_title="Create Notes: choose a library, genre, artist or album folder")


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


def music_hooks(engine: NotesEngine, kinds: tuple = (KIND_ARTIST,)) -> ReviewHooks:
    from gui.music_evidence_view import LocalEvidenceView

    offer_albums = tuple(kinds) == (KIND_ARTIST,)
    return ReviewHooks(
        level_labels=LEVEL_LABELS, current_level_key=lambda p: _CURRENT_LEVEL_KEY.get(getattr(p, "level", ""), ""),
        skip_level=SUGGEST_SKIP, local_level=LEVEL_LOCAL_TAGS, local_label=LOCAL_LABEL, local_tooltip=LOCAL_TOOLTIP,
        can_make_local=lambda p: p.kind in (KIND_ARTIST, KIND_ALBUM) and p.note_kind in ("artist", "album"),
        link_placeholder=_link_placeholder, check_link=check_link, link_errors=(LinkError,), genres_of=_genres_of,
        evidence_view=LocalEvidenceView,
        evidence_applies=lambda p: p.kind in (KIND_ARTIST, KIND_ALBUM) and p.note_kind != "about",
        best_guess=engine.best_guess, why_not=engine.why_cannot_choose,
        followup_kind=KIND_ARTIST if offer_albums else "", followup_label=FOLLOWUP_LABEL, followup_tooltip=FOLLOWUP_TOOLTIP,
        followup_question=(lambda n: f"{n} artist note{'' if n == 1 else 's'} written.\n\nCreate the album notes for "
                                     f"{'this artist' if n == 1 else 'these artists'} too? (slower: one lookup per album)")
        if offer_albums else None,
        log=_log if notes_debug.enabled() else None, recycle_note=RECYCLE_NOTE)


# ---- the run ----------------------------------------------------------------------------------------------------------

def _label(target) -> str:
    folder = target.folder
    return f"{folder.parent.name} / {folder.name}" if target.kind == KIND_ALBUM else folder.name


def _nothing_found_why(found) -> str:
    wrong = found.wrong_level_message("tick it under 'What to create'")
    if wrong:  # an album folder asked for artist notes only: say so, it is not a library root
        return wrong
    return LIBRARY_ROOT_MESSAGE if found.only_a_library_root else ""


def _found_notes(found) -> list[str]:
    if not found.groupings:
        return []
    return [f"{len(found.groupings)} alphabetical grouping folder(s) (A, B-C, 0-9...) skipped: no note, no proposal."]


def left_alone_sentence(found) -> str:
    """'N notes were left alone: edited by a person or not ours.' (and how many are already current)."""
    left = sum(1 for x in found.skipped if x.state in ("edited", "foreign"))
    current = sum(1 for x in found.skipped if x.state == "current")
    return f"{left} notes were left alone: edited by a person or not ours." + (f" {current} are already current." if current else "")


def create_notes(
    parent: QWidget, paths: list, include_subfolders: bool, make_fetchers: Callable[[], Fetchers] = live_fetchers,
    size_text: str = "", on_size: Optional[Callable[[str], None]] = None, open_path: Callable[[str], None] = open_in_system,
    kinds: tuple = (KIND_ARTIST,), cache=None, include_outdated: bool = False, discogs_mode: Optional[str] = None,
    singles: Optional[bool] = None,
) -> Optional[NotesReviewDialog]:
    """Scan `paths`, look every folder up under a cancellable progress dialog, then open the review page. 'Create the album
    notes for these artists too' runs once more for those artists' albums. Returns the (closed) last dialog, or None when
    there was nothing to review. The engine's options default to Preferences (core/music/settings.py)."""
    from core import history
    from core.music import settings as music_settings

    options = music_settings.engine_options()
    discogs_mode = discogs_mode or options["discogs_mode"]
    singles = options["singles"] if singles is None else singles
    music_settings.apply_number_words()
    kinds = parse_kinds(kinds)
    fetchers = make_fetchers()
    fetchers.wikipedia = fetchers.wikipedia and notes_settings.wikipedia_enabled()
    engine = NotesEngine(fetchers, cache=cache, discogs_mode=discogs_mode, singles=singles)
    notes = [music_scope.kinds_sentence(kinds)] + ([DISCOGS_NOTE] if fetchers.discogs is None else [])

    def rebuild(proposal: Proposal, candidate: Optional[Candidate], level: str = "", **extra) -> Proposal:
        return engine.rebuild(proposal, candidate=candidate, level=level, **extra)

    try:
        dialog = run_create_notes(
            parent, title=TITLE, scan=lambda: scan(paths, include_subfolders, kinds=kinds, include_outdated=include_outdated),
            engine=engine, build=build_proposals, write_fn=write_proposal, label_for=_label,
            nothing_found="No artist or album folders without a note were found.", intro_notes=notes,
            owner_kinds=(KIND_ARTIST, KIND_GENRE), child_kind=KIND_ALBUM, size_text=size_text, on_size=on_size,
            open_path=open_path, include_outdated=include_outdated, left_alone=left_alone_sentence,
            candidate_columns=CANDIDATE_COLUMNS,
            history_note="Recorded in Tools > History (it is switched on)." if history.history_enabled() else "",
            hooks=music_hooks(engine, kinds), rebuild=rebuild, nothing_found_why=_nothing_found_why,
            found_notes=_found_notes)
    finally:
        engine.close()
    if dialog is not None and dialog.followup:  # 'Create the album notes for these artists too': only those artists' albums
        return create_notes(parent, dialog.followup, True, make_fetchers, size_text, on_size, open_path,
                            kinds=(KIND_ALBUM,), cache=cache, include_outdated=include_outdated,
                            discogs_mode=discogs_mode, singles=singles)
    return dialog
