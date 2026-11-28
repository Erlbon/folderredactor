"""
core/comicnotes/flow.py

The engine behind Notes > Look Up for a COMICS library (plan step 18; Erlend's D32, D34-D36, 2026-11-21). Same shape as
books' (core/booknotes/flow.py): Qt-free, every network call through an injectable fetch, nothing written here.

D33, changed 2026-11-21: the comics' own ComicInfo.xml and the folder names only. No Comic Vine, no Bedetheque ("leave
out. by that logic, it undoes the reason why we split folder redactor into a seperate app"). The one network source left
is Wikipedia, for the groupings (D34A), as for music genres and book genres.

  scan(paths, include_subfolders, kinds)   core/comics.py's levels; one folder only when include_subfolders is off
  NotesEngine.build_proposal(target)       series.md / a grouping's about.md

What each note is built from:

  series    the title and years from the folder name ('Asterix (1961-)'). From the ComicInfo.xml of the comics lying in it
            (at most local.MAX_COMICS_READ opened): the credits (the most common names), the publisher, the genres; the
            album list (number, title, year) from ComicInfo, else from the file names. D32B: the list only when the series
            has fewer than render.ALBUM_LIST_MAX albums (ComicInfo's Count when it says more); none for a run split by year
            folders ('Robbedoes (1938-2005)/1943 (35 issues)'), whose credits come from the comics of its first year.
            No summary: ComicInfo's Summary describes one album, not the series.
            Confident when at least one comic has a ComicInfo.xml; built from file names only: uncertain, to be checked.
  grouping  a publisher, lineage, country, continent or underscore grouping (D35A: looked up like a publisher). The title
            and years from the folder name ('_Dupuis (1922-)' -> 'Dupuis', '1922-'). A short Wikipedia paragraph: English
            first, else the country folder's language, untranslated (D36B). No page: title and years only (D34A).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from core import comics as levels
from core import notes_engine
from core.comicnotes.local import FolderComics, country_languages, folder_title, folder_years, read_albums, year_folders
from core.comicnotes.render import (
    ALBUM_LIST_MAX, COMICINFO_CREDIT, FILE_NAMES_CREDIT, album_line, render_grouping_note, render_local_note,
    render_series_note,
)
from core.notes_engine import record_note_created, summarize, undo_note_entry, write_proposal  # noqa: F401 -- re-exported
from core.comics import COMIC_EXTENSIONS
from core.shelf_scan import ShelfScan, Skipped, Target, entries, has_extension  # noqa: F401 -- re-exported
from redactor_common.core import note_text
from redactor_common.core import wikipedia as wp
from redactor_common.core.local_db import normalize_words
from redactor_common.core.notes_cache import CachedFetch, RequestStats, ResponseCache
from redactor_common.core.notes_model import KIND_NOTE, STATUS_SKIPPED, Candidate, Confidence, NotesSummary  # noqa: F401
from redactor_common.core.notes_model import Proposal
from redactor_common.core.notes_phases import PhaseSet, PhaseTimer

ALL_KINDS = levels.ALL_KINDS
KIND_SERIES, KIND_GROUPING = levels.KIND_SERIES, levels.KIND_GROUPING
LEVEL_LOCAL_NAME = "local-name"
YEAR_RUN_READ = 10  # comics opened in the first year folder of a run split by year
# a Wikipedia introduction about a publisher, an imprint, a magazine or a country's comics names one of these (any of the
# languages tried; accents dropped, a word counts when it starts with one: 'comic' finds 'comics')
COMIC_WORDS = (
    "comic", "cartoon", "graphic novel", "manga", "publish", "imprint", "magazine", "periodical", "strip",
    "bande dessinee", "bandes dessinees", "editeur", "edition", "periodique", "illustre", "hebdomadaire",
    "stripverhaal", "uitgever", "tijdschrift", "weekblad", "verlag", "zeitschrift", "fumett", "editor", "rivista",
    "historieta", "revista", "quadrinhos", "banda desenhada", "tegneserie", "forlag", "tecknad", "serietidning",
    "sarjakuva", "kustanta",
)

WIKIPEDIA, READ, SCAN, WRITE = "wikipedia", "read", "scan", "write"
PHASES = PhaseSet({SCAN: "scan", READ: "reading comics", WIKIPEDIA: "Wikipedia", WRITE: "writing"},
                  {SCAN: "folders", READ: "folders", WIKIPEDIA: "requests", WRITE: "notes"})

Progress = Callable[[int, int, str], None]


@dataclass
class Fetchers:
    """The network, injectable. `wiki` is `fetch(url) -> bytes` (None: the real one); `wikipedia` False leaves Wikipedia
    out (groupings then get their title and years only)."""

    wiki: Optional[Callable] = None
    wikipedia: bool = True


def live_fetchers() -> Fetchers:
    return Fetchers()


def scan(paths: Iterable, include_subfolders: bool = True, kinds: Iterable[str] = ALL_KINDS, include_outdated: bool = False,
         on_folder=None) -> ShelfScan:
    """core/comics.py's scan. Its levels are only known from below, so it always walks down; with `include_subfolders` off
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


def _page_url(page: wp.Page, lang: str) -> str:
    return page.url or f"https://{lang}.wikipedia.org/wiki/{page.title.replace(' ', '_')}"


class NotesEngine:
    """Builds comics proposals. One engine per run: it keeps what it fetched and the request statistics."""

    def __init__(self, fetchers: Optional[Fetchers] = None, cache: Optional[ResponseCache] = None):
        self.fetchers = fetchers or Fetchers()
        self.stats = RequestStats()
        self.phases = PhaseTimer(PHASES)
        self._wiki = CachedFetch(self.fetchers.wiki or notes_engine.wiki_fetch(), "wiki", cache, self.stats, self.phases,
                                 WIKIPEDIA)

    def close(self) -> None:
        """Nothing to release (the cache is the caller's)."""

    # -- the engine interface -----------------------------------------------------------------------------------

    def build_proposal(self, target: Target) -> Proposal:
        return self._build(target)

    def rebuild(self, proposal: Proposal, candidate: Optional[Candidate] = None, level: str = "") -> Proposal:
        if level == LEVEL_LOCAL_NAME:
            return self.local_note(proposal)
        return self._build(proposal.target)  # type: ignore[arg-type]

    def can_choose(self, proposal: Proposal, candidate: Candidate) -> bool:
        return False  # nothing is searched for, so there are no candidates to choose from

    def best_guess(self, proposal: Proposal) -> Optional[Candidate]:
        return None

    def local_note(self, proposal: Proposal) -> Proposal:
        name = proposal.target.folder.name  # type: ignore[attr-defined]
        title = folder_title(name)
        return Proposal(proposal.target, Confidence.CONFIDENT, render_local_note(title, folder_years(name)), title,
                        ["a minimal note from the folder name, as you asked"], ["the folder name"])

    # -- building -----------------------------------------------------------------------------------------------

    def _build(self, target: Target) -> Proposal:
        proposal = Proposal(target, title=folder_title(target.folder.name))
        try:
            if target.kind == KIND_SERIES:
                return self._series(proposal)
            return self._grouping(proposal)
        except wp.WikipediaError as exc:
            proposal.problems.append(str(exc))
            return proposal

    # -- series ---------------------------------------------------------------------------------------------------

    def _series(self, proposal: Proposal) -> Proposal:
        folder: Path = proposal.target.folder  # type: ignore[attr-defined]
        title = proposal.title
        years = folder_years(folder.name)
        years_run = [] if has_extension(entries(folder)[0], COMIC_EXTENSIONS) else year_folders(folder)
        with self.phases.phase(READ):
            found: FolderComics = read_albums(years_run[0], YEAR_RUN_READ, title) if years_run else read_albums(
                folder, series=title)
        lines: list[str] = []
        if years_run:
            proposal.reasons.append(f"a run split into {len(years_run)} year folders: no album list (D32B)")
            if not years:
                first, last = folder_title(years_run[0].name), folder_title(years_run[-1].name)
                years = first if first == last else f"{first}-{last}"
        else:
            total = max(found.count, len(found.albums))
            if total < ALBUM_LIST_MAX:
                lines = [album_line(a.title, a.year, a.number) for a in found.albums]
            else:
                proposal.reasons.append(f"{total} albums: no album list (D32B: fewer than {ALBUM_LIST_MAX} only)")
            if not years and found.first_year:
                years = found.first_year if found.first_year == found.last_year else f"{found.first_year}-{found.last_year}"
                proposal.reasons.append("the years are those of the albums in the folder, not of the whole series")
        if found.with_comicinfo:
            proposal.confidence = Confidence.CONFIDENT
            proposal.sources = ["ComicInfo.xml"]
            proposal.reasons.append(f"{found.with_comicinfo} of the comics read carry a ComicInfo.xml")
            footer = [COMICINFO_CREDIT]
        else:
            proposal.confidence = Confidence.UNCERTAIN
            proposal.sources = ["the file names"]
            proposal.reasons.append("no comic here carries a ComicInfo.xml (or none is a .cbz): built from the folder and "
                                    "file names; check it")
            footer = [FILE_NAMES_CREDIT]
        proposal.note_text = render_series_note(title, years=years, genres=found.genres, credits=found.credits,
                                                publisher=found.publisher, lines=lines, footer=footer)
        return proposal

    # -- grouping -------------------------------------------------------------------------------------------------

    def _grouping(self, proposal: Proposal) -> Proposal:
        folder: Path = proposal.target.folder  # type: ignore[attr-defined]
        title = proposal.title
        years = folder_years(folder.name)
        found = self._grouping_page(proposal, title, country_languages(folder)) if self.fetchers.wikipedia else None
        if not self.fetchers.wikipedia:
            proposal.reasons.append("Wikipedia is switched off for this run: title and years only")
        proposal.confidence = Confidence.CONFIDENT
        if found is None:
            proposal.sources = ["the folder name"]
            proposal.note_text = render_grouping_note(title, years=years)
            return proposal
        page, lang = found
        proposal.sources = ["Wikipedia"]
        proposal.note_text = render_grouping_note(title, years=years, intro=wp.trim_extract(page.extract),
                                                  links=[_page_url(page, lang)],
                                                  footer=[note_text.wikipedia_credit(page.title, lang)])
        return proposal

    def _fits(self, page: Optional[wp.Page], title: str) -> bool:
        return (page is not None and _fold(title) in _fold(page.title)
                and _mentions_any(page.extract + " " + page.description, COMIC_WORDS))

    def _grouping_page(self, proposal: Proposal, title: str, languages: tuple[str, ...]) -> Optional[tuple[wp.Page, str]]:
        """English first: the likely article names, then a search; then the country folder's languages (D36B)."""
        for lang in ("en", *[x for x in languages if x != "en"]):
            tried: set[str] = set()
            guesses = ((f"{title} Comics", f"{title} (publisher)", f"{title} (comics)", f"{title} comics", title)
                       if lang == "en" else (title,))
            for guess in guesses:
                tried.add(guess)
                page = wp.usable(wp.get_summary(guess, self._wiki, lang))
                if self._fits(page, title):
                    proposal.reasons.append(f"Wikipedia ({lang}): {page.title}")  # type: ignore[union-attr]
                    return page, lang  # type: ignore[return-value]
            query = f"{title} comics" if lang == "en" else title
            for hit in wp.search_titles(query, self._wiki, limit=5, lang=lang):
                if hit.title in tried or _fold(title) not in _fold(hit.title):
                    continue
                tried.add(hit.title)
                page = wp.usable(wp.get_summary(hit.title, self._wiki, lang))
                if self._fits(page, title):
                    proposal.reasons.append(f"Wikipedia ({lang}): {page.title}, found by a search")  # type: ignore[union-attr]
                    return page, lang  # type: ignore[return-value]
        where = "English" + "".join(f", {x}" for x in languages if x != "en")
        proposal.reasons.append(f"no Wikipedia article about {title} in {where}: title and years only (D34A)")
        return None


def build_proposals(
    targets: list[Target], fetchers: Optional[Fetchers] = None, progress: Optional[Progress] = None,
    cancel: Optional[Callable[[], bool]] = None, on_proposal: Optional[Callable[[Proposal], None]] = None,
    engine: Optional[NotesEngine] = None, cache: Optional[ResponseCache] = None,
) -> list[Proposal]:
    """One Proposal per target, in order. Wikipedia only (for groupings); this function writes no file."""
    engine = engine or NotesEngine(fetchers, cache)
    return notes_engine.build_proposals(targets, engine, progress, cancel, on_proposal)
