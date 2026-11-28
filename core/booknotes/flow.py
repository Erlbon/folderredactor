"""
core/booknotes/flow.py

The engine behind Notes > Look Up for a BOOKS library (plan step 17; Erlend's D27-D31, 2026-11-21). Same shape as video's
(core/video/flow.py): Qt-free, every network call through an injectable fetch, nothing written here.

  scan(paths, include_subfolders, kinds)   core/books.py's levels; one folder only when include_subfolders is off
  NotesEngine.build_proposal(target)       author.md / series.md / a genre's about.md

What each note is built from:

  author   the name from the folder ('Banks, Iain M.' -> 'Iain M. Banks'). The book list from the local ISFDB database when
           the author is in it (D28B: series and their order are ISFDB's strength), else from Open Library. The years and
           the Wikidata id from Open Library; the introduction from the Wikipedia article that Wikidata id points to, or,
           without one, an article found by name whose introduction calls the person a writer.
           Confident when ISFDB has the exact name, or Open Library has exactly one author of that name (or, of several,
           exactly one whose books include books in the folder). Several of one name: uncertain, the candidates listed.
  series   the series' name from the folder, its author from the folder above. The reading order from ISFDB; without it,
           from the books in the folder (their own OPF series numbers: uncertain, since it lists only what is there). The
           description from a Wikipedia article whose introduction names the author.
  genre    the genre's name from the folder ('813 - Fantasy' -> 'Fantasy'); a Wikipedia article about it (D31A, as for
           music). Nothing found: no note.

D30A: single books get no note (the book carries its own description), so a Calibre book folder is never a target.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from core import books as levels
from core import notes_engine
from core.booknotes import settings as book_settings
from core.booknotes.isfdb import IsfdbBooks, IsfdbError, Work
from core.booknotes.local import LocalBook, author_name, genre_title, is_author_folder, read_books, series_title
from core.booknotes.openlibrary import CREDIT as OL_CREDIT
from core.booknotes.openlibrary import OlAuthor, OlWork, OpenLibrary, OpenLibraryError, make_fetch as make_ol_fetch
from core.booknotes.render import (
    ISFDB_CREDIT, LOCAL_BOOKS_CREDIT, book_line, render_author_note, render_genre_note, render_local_note,
    render_series_note,
)
from core.notes_engine import record_note_created, summarize, undo_note_entry, write_proposal  # noqa: F401 -- re-exported
from core.shelf_scan import ShelfScan, Skipped, Target  # noqa: F401 -- re-exported
from redactor_common.core import note_text
from redactor_common.core import wikipedia as wp
from redactor_common.core.local_db import normalize_words
from redactor_common.core.notes_cache import CachedFetch, RequestStats, ResponseCache
from redactor_common.core.notes_model import KIND_NOTE, STATUS_SKIPPED, Candidate, Confidence, NotesSummary  # noqa: F401
from redactor_common.core.notes_model import Proposal as _Proposal
from redactor_common.core.notes_phases import PhaseSet, PhaseTimer

ALL_KINDS = levels.ALL_KINDS
KIND_AUTHOR, KIND_SERIES, KIND_GENRE = levels.KIND_AUTHOR, levels.KIND_SERIES, levels.KIND_GENRE
LEVEL_LOCAL_NAME = "local-name"
MAX_CANDIDATES = 4
OTHER_BOOKS = "Other books"
WRITER_WORDS = ("writer", "novelist", "author", "poet", "playwright", "essayist", "journalist")
GENRE_WORDS = ("genre", "fiction", "literature", "novels", "literary")
SERIES_WORDS = ("series", "novel", "trilogy", "sequence", "saga", "books")

ISFDB, OPEN_LIBRARY, WIKIPEDIA, SCAN, WRITE = "isfdb", "openlibrary", "wikipedia", "scan", "write"
PHASES = PhaseSet({SCAN: "scan", ISFDB: "ISFDB", OPEN_LIBRARY: "Open Library", WIKIPEDIA: "Wikipedia", WRITE: "writing"},
                  {SCAN: "folders", ISFDB: "searches", OPEN_LIBRARY: "requests", WIKIPEDIA: "requests", WRITE: "notes"})

Progress = Callable[[int, int, str], None]


@dataclass
class Fetchers:
    """The network, injectable. `openlibrary` and `wiki` are `fetch(url) -> bytes` (None: the real ones); `wikipedia` False
    leaves Wikipedia out; `isfdb` is the database path (None: the setting; '' : none)."""

    openlibrary: Optional[Callable] = None
    wiki: Optional[Callable] = None
    wikipedia: bool = True
    isfdb: Optional[str] = None


def live_fetchers() -> Fetchers:
    return Fetchers()


@dataclass
class Proposal(_Proposal):
    """The shared draft of one note plus what only a book folder has."""

    ol_key: str = ""  # the Open Library author the draft is built from

    def to_dict(self, with_text: bool = True) -> dict:
        out = super().to_dict(with_text)
        if self.ol_key:
            out["openlibrary"] = self.ol_key
        return out


def scan(paths: Iterable, include_subfolders: bool = True, kinds: Iterable[str] = ALL_KINDS, include_outdated: bool = False,
         on_folder=None) -> ShelfScan:
    """core/books.py's scan. Its levels are only known from below, so it always walks down; with `include_subfolders` off
    only the folders asked about are kept (Look Up on one folder: that folder, as what it is)."""
    paths = list(paths)
    found = levels.scan(paths, True, kinds, include_outdated, on_folder)
    if include_subfolders:
        return found
    asked = {os.path.normcase(str(Path(p))) for p in paths}
    found.targets = [t for t in found.targets if os.path.normcase(str(t.folder)) in asked]
    found.skipped = [s for s in found.skipped if os.path.normcase(str(s.folder)) in asked]
    return found


def _fold(text: str) -> str:
    return normalize_words(text)


def _mentions_any(text: str, words: Iterable[str]) -> bool:
    low = f" {_fold(text)} "
    return any(f" {w}" in low for w in words)


def _surname(name: str) -> str:
    words = _fold(name).split()
    return words[-1] if words else ""


class NotesEngine:
    """Builds book proposals. One engine per run: it keeps what it fetched and the request statistics."""

    def __init__(self, fetchers: Optional[Fetchers] = None, cache: Optional[ResponseCache] = None):
        self.fetchers = fetchers or Fetchers()
        self.stats = RequestStats()
        self.phases = PhaseTimer(PHASES)
        self._ol_fetch = CachedFetch(self.fetchers.openlibrary or make_ol_fetch(), "openlibrary", cache, self.stats,
                                     self.phases, OPEN_LIBRARY)
        self._wiki = CachedFetch(self.fetchers.wiki or notes_engine.wiki_fetch(), "wiki", cache, self.stats, self.phases,
                                 WIKIPEDIA)
        self.ol = OpenLibrary(self._ol_fetch)
        path = book_settings.isfdb_path() if self.fetchers.isfdb is None else self.fetchers.isfdb
        self.isfdb: Optional[IsfdbBooks] = None
        self.isfdb_problem = ""
        if path:
            try:
                self.isfdb = IsfdbBooks(path)
            except IsfdbError as exc:
                self.isfdb_problem = f"the ISFDB database cannot be used ({exc}): Open Library only"
        self._works: dict[str, list[Work]] = {}

    def close(self) -> None:
        """Nothing to release (the database is shared for the session, the cache is the caller's)."""

    # -- the engine interface -----------------------------------------------------------------------------------

    def build_proposal(self, target: Target) -> Proposal:
        return self._build(target)

    def rebuild(self, proposal: Proposal, candidate: Optional[Candidate] = None, level: str = "") -> Proposal:
        if level == LEVEL_LOCAL_NAME:
            return self.local_note(proposal)
        return self._build(proposal.target, force=candidate)  # type: ignore[arg-type]

    def can_choose(self, proposal: Proposal, candidate: Candidate) -> bool:
        return candidate.source == "openlibrary" and bool(candidate.id)

    def best_guess(self, proposal: Proposal) -> Optional[Candidate]:
        """The top candidate when it alone has books that are in the folder (score 1.0 or more)."""
        ranked = sorted(proposal.candidates, key=lambda c: -c.score)
        if not ranked or ranked[0].score < 1.0:
            return None
        return ranked[0] if len(ranked) == 1 or ranked[1].score < ranked[0].score else None

    def local_note(self, proposal: Proposal) -> Proposal:
        target = proposal.target
        title = self._title_of(target)  # type: ignore[arg-type]
        return Proposal(target, Confidence.CONFIDENT, render_local_note(title), title,
                        ["a minimal note from the folder name, as you asked"], ["the folder name"])

    # -- building -----------------------------------------------------------------------------------------------

    @staticmethod
    def _title_of(target: Target) -> str:
        name = target.folder.name
        if target.kind == KIND_AUTHOR:
            return author_name(name)
        if target.kind == KIND_SERIES:
            return series_title(name)
        return genre_title(name)

    def _build(self, target: Target, force: Optional[Candidate] = None) -> Proposal:
        proposal = Proposal(target, title=self._title_of(target))
        if self.isfdb_problem:
            proposal.problems.append(self.isfdb_problem)
        try:
            if target.kind == KIND_AUTHOR:
                return self._author(proposal, force)
            if target.kind == KIND_SERIES:
                return self._series(proposal)
            return self._genre(proposal)
        except (OpenLibraryError, wp.WikipediaError) as exc:
            proposal.problems.append(str(exc))
            return proposal

    def _isfdb_works(self, name: str) -> list[Work]:
        if self.isfdb is None:
            return []
        key = _fold(name)
        if key not in self._works:
            with self.phases.phase(ISFDB):
                try:
                    self._works[key] = self.isfdb.author_works(name)
                except IsfdbError as exc:
                    self.isfdb_problem = f"the ISFDB database could not be searched ({exc})"
                    self._works[key] = []
        return self._works[key]

    # -- author ---------------------------------------------------------------------------------------------------

    def _author(self, proposal: Proposal, force: Optional[Candidate]) -> Proposal:
        name = proposal.title
        local = read_books(proposal.target.folder)  # type: ignore[attr-defined]
        local_titles = {_fold(b.title) for b in local if b.title}
        works = self._isfdb_works(name)
        chosen: Optional[OlAuthor] = None
        if force is not None:
            chosen = self.ol.author(force.id)
            if chosen is None:
                proposal.problems.append(f"Open Library has no author {force.id} any more")
                return proposal
            proposal.reasons.append("chosen by you from the candidates")
        else:
            chosen = self._pick_author(proposal, name, local_titles, bool(works))
        if chosen is None and not works:
            if not proposal.candidates:
                proposal.reasons.append(f"neither the ISFDB database nor Open Library has an author called '{name}'")
            return proposal
        if works:
            proposal.reasons.append(f"ISFDB has {len(works)} books by {name}")
        details = self.ol.author(chosen.key) if chosen is not None and not chosen.wikidata else chosen
        details = details or chosen
        ol_works: list[OlWork] = [] if works or chosen is None else self.ol.works(chosen.key)
        return self._finish_author(proposal, name, details, works, ol_works, local)

    def _pick_author(self, proposal: Proposal, name: str, local_titles: set[str], in_isfdb: bool) -> Optional[OlAuthor]:
        hits = self.ol.search_authors(name)
        exact = [a for a in hits if _fold(a.name) == _fold(name)]
        proposal.candidates = [Candidate("openlibrary", a.key, a.name, ", ".join(x for x in (a.years, a.top_work) if x),
                                         [], 0.5 + (0.3 if a in exact else 0.0)) for a in hits[:MAX_CANDIDATES]]
        if len(exact) == 1:
            proposal.reasons.append(f"the only Open Library author called '{exact[0].name}'")
            return exact[0]
        if len(exact) > 1:
            scored = []
            for author in exact[:MAX_CANDIDATES]:
                titles = {_fold(w.title) for w in self.ol.works(author.key)}
                shared = sorted(titles & local_titles)
                scored.append((len(shared), author))
                for c in proposal.candidates:
                    if c.id == author.key:
                        c.score += len(shared)
                        c.hits = [t for t in shared][:5]
            scored.sort(key=lambda pair: -pair[0])
            if scored[0][0] > 0 and (len(scored) == 1 or scored[1][0] < scored[0][0]):
                proposal.reasons.append(f"{len(exact)} Open Library authors are called '{name}'; only one has books that "
                                        f"are in the folder ({scored[0][0]})")
                return scored[0][1]
            if not in_isfdb:
                proposal.reasons.append(f"{len(exact)} Open Library authors are called '{name}': pick the right one")
                proposal.confidence = Confidence.UNCERTAIN
            return None
        if hits and not in_isfdb:
            proposal.reasons.append(f"no Open Library author is exactly '{name}': the closest are listed")
            proposal.confidence = Confidence.UNCERTAIN
        return None

    def _finish_author(self, proposal: Proposal, name: str, author: Optional[OlAuthor], works: list[Work],
                       ol_works: list[OlWork], local: list[LocalBook]) -> Proposal:
        links: list[str] = []
        footer: list[str] = []
        sources: list[str] = []
        groups: list[tuple[str, list[str]]] = []
        if works:
            series: dict[str, list[Work]] = {}
            other: list[Work] = []
            for w in works:
                (series.setdefault(w.series, []) if w.series else other).append(w)
            for title in sorted(series, key=lambda s: min((w.year or "9999") for w in series[s])):
                ordered = sorted(series[title], key=lambda w: (w.sort_number(), w.year or "9999"))
                groups.append((title, [book_line(w.title, w.year) for w in ordered]))
            if other:
                groups.append((OTHER_BOOKS if series else "", [book_line(w.title, w.year) for w in other]))
            sources.append("ISFDB")
            footer.append(ISFDB_CREDIT)
        elif ol_works:
            groups.append(("", [book_line(w.title, w.year) for w in ol_works]))
        if author is not None:
            proposal.ol_key = author.key
            links.append(author.url)
            sources.append("Open Library")
            if not works:
                footer.append(OL_CREDIT)
        intro = ""
        page = self._author_page(proposal, name, author)
        if page is not None:
            intro = wp.trim_extract(page.extract)
            links.insert(0, page.url or f"https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')}")
            footer.append(note_text.wikipedia_credit(page.title))
            sources.append("Wikipedia")
        proposal.sources = sources
        proposal.confidence = Confidence.CONFIDENT
        proposal.note_text = render_author_note(name, years=author.years if author else "", intro=intro, groups=groups,
                                                links=links, footer=footer)
        return proposal

    def _author_page(self, proposal: Proposal, name: str, author: Optional[OlAuthor]) -> Optional[wp.Page]:
        if not self.fetchers.wikipedia:
            proposal.reasons.append("Wikipedia is switched off for this run")
            return None
        if author is not None and author.wikidata:
            title = wp.title_from_wikidata(author.wikidata, self._wiki)
            page = wp.usable(wp.get_summary(title, self._wiki)) if title else None
            if page is not None:
                proposal.reasons.append(f"Wikipedia: {page.title}, through Open Library's Wikidata link")
                return page
        for hit in wp.search_titles(name, self._wiki, limit=3):
            if _fold(wp.strip_parenthetical(hit.title)) != _fold(name):
                continue
            page = wp.usable(wp.get_summary(hit.title, self._wiki))
            if page is not None and _mentions_any(page.extract + " " + page.description, WRITER_WORDS):
                proposal.reasons.append(f"Wikipedia: {page.title}, found by name (its introduction calls them a writer)")
                return page
        proposal.reasons.append(f"no Wikipedia article about the writer {name} was found")
        return None

    # -- series ---------------------------------------------------------------------------------------------------

    def _series(self, proposal: Proposal) -> Proposal:
        folder: Path = proposal.target.folder  # type: ignore[attr-defined]
        title = proposal.title
        author = author_name(folder.parent.name) if is_author_folder(folder.parent) else ""
        lines: list[str] = []
        footer: list[str] = []
        sources: list[str] = []
        confidence = Confidence.CONFIDENT
        works = self.isfdb.series_works(title, author) if self.isfdb is not None and author else []
        if works:
            lines = [book_line(w.title, w.year, w.number) for w in works]
            proposal.reasons.append(f"ISFDB has {len(works)} books in {title} by {author}")
            footer.append(ISFDB_CREDIT)
            sources.append("ISFDB")
        else:
            local = [b for b in read_books(folder) if b.number]
            local.sort(key=lambda b: (float(b.number) if b.number.replace(".", "", 1).isdigit() else 1e9, b.title))
            if local:
                lines = [book_line(b.title, b.year, b.number) for b in local]
                footer.append(LOCAL_BOOKS_CREDIT)
                sources.append("the books' own OPF")
                proposal.reasons.append(f"ISFDB has no series '{title}'" + (f" by {author}" if author else "")
                                        + ": the order is only the books in the folder; check it")
                confidence = Confidence.UNCERTAIN
            else:
                proposal.reasons.append(f"no reading order: ISFDB has no series '{title}' and the books carry no numbers")
        page = self._series_page(proposal, title, author)
        links: list[str] = []
        intro = ""
        if page is not None:
            intro = wp.trim_extract(page.extract)
            links.append(page.url or f"https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')}")
            footer.append(note_text.wikipedia_credit(page.title))
            sources.append("Wikipedia")
        if not lines and page is None:
            return proposal  # nothing found: no note (a person can still ask for the minimal one)
        proposal.sources = sources
        proposal.confidence = confidence
        proposal.note_text = render_series_note(title, author=author, intro=intro, lines=lines, links=links, footer=footer)
        return proposal

    def _series_page(self, proposal: Proposal, title: str, author: str) -> Optional[wp.Page]:
        if not self.fetchers.wikipedia:
            return None
        surname = _surname(author)
        tried: set[str] = set()
        for query in (f"{title} (series)", f"{title} (novel series)", f"{title} series", title):
            for hit in wp.search_titles(query, self._wiki, limit=3):
                if hit.title in tried:
                    continue
                tried.add(hit.title)
                if _fold(title) not in _fold(hit.title):
                    continue
                page = wp.usable(wp.get_summary(hit.title, self._wiki))
                if page is None:
                    continue
                text = page.extract + " " + page.description
                if surname and surname in _fold(text).split() and _mentions_any(text, SERIES_WORDS):
                    proposal.reasons.append(f"Wikipedia: {page.title} (its introduction names {author})")
                    return page
        proposal.reasons.append(f"no Wikipedia article about the series {title}" + (f" by {author}" if author else ""))
        return None

    # -- genre ----------------------------------------------------------------------------------------------------

    def _genre(self, proposal: Proposal) -> Proposal:
        title = proposal.title
        if not self.fetchers.wikipedia:
            proposal.reasons.append("Wikipedia is switched off for this run, and a genre note is its paragraph")
            return proposal
        for query in (f"{title} fiction", f"{title} literature", f"{title} (genre)", title):
            page = wp.usable(wp.get_summary(query, self._wiki))
            if page is None:
                continue
            if _fold(title) in _fold(page.title) and _mentions_any(page.extract + " " + page.description, GENRE_WORDS):
                proposal.reasons.append(f"Wikipedia: {page.title}")
                proposal.sources = ["Wikipedia"]
                proposal.confidence = Confidence.CONFIDENT
                proposal.note_text = render_genre_note(
                    title, intro=wp.trim_extract(page.extract),
                    links=[page.url or f"https://en.wikipedia.org/wiki/{page.title.replace(' ', '_')}"],
                    footer=[note_text.wikipedia_credit(page.title)])
                return proposal
        proposal.reasons.append(f"no Wikipedia article about the genre {title}")
        return proposal


def build_proposals(
    targets: list[Target], fetchers: Optional[Fetchers] = None, progress: Optional[Progress] = None,
    cancel: Optional[Callable[[], bool]] = None, on_proposal: Optional[Callable[[Proposal], None]] = None,
    engine: Optional[NotesEngine] = None, cache: Optional[ResponseCache] = None,
) -> list[Proposal]:
    """One Proposal per target, in order. Network only; this function writes no file."""
    engine = engine or NotesEngine(fetchers, cache)
    return notes_engine.build_proposals(targets, engine, progress, cancel, on_proposal)
