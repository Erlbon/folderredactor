"""
core/comicnotes/render.py

The texts of the comics notes (Erlend's D32, D34, D35, 2026-11-21; D33 changed the same day: the comics' own ComicInfo.xml
and the folder names only). Pure: the same inputs always give the same note. The writing itself (never overwriting,
status: draft) is redactor_common's core/notes.py.

  series.md   front matter (title, years, genres), the credits and the publisher as fact lines, "## Albums" ('- 1. Title
              (Year)') when the series has fewer than ALBUM_LIST_MAX albums; none for long weekly runs
  about.md    (a publisher, lineage, country or underscore grouping) front matter with the folder's years, a short
              Wikipedia paragraph; the title and years only when no page is found
"""

from __future__ import annotations

from typing import Iterable

from core.version import APP_VERSION
from redactor_common.core.note_text import credit_footer, fact_lines, join_blocks
from redactor_common.core.notes import NoteFrontMatter, render_note

CURRENT_NOTE_FORMAT = 2  # the stamped shape (redactor_common core/notes.py); bump when a change is worth a refresh
ALBUM_LIST_MAX = 100  # D32B: a list of albums when the series has fewer than about 100
COMICINFO_CREDIT = "Built from the comics' own ComicInfo.xml"
FILE_NAMES_CREDIT = "Built from the folder and the comics' file names"
LOCAL_ONLY_CREDIT = "Built from the folder only, no online source"


def generator_text() -> str:
    return f"folderredactor {APP_VERSION}"


def album_line(title: str, year: str = "", number: str = "") -> str:
    """'- 1. Asterix the Gaul (1961)'; an album known only by its number is '- #12 (1971)'; nothing known: ''."""
    if title:
        name = (f"{number}. " if number else "") + title
    elif number:
        name = f"#{number}"
    else:
        return ""
    return f"- {name}" + (f" ({year})" if year else "")


def _front(title: str, years: str = "", genres: Iterable[str] = (), links: Iterable[str] = ()) -> NoteFrontMatter:
    return NoteFrontMatter(title=title, years=years, genres=[g.lower() for g in genres if g], links=[u for u in links if u],
                           generator=generator_text(), note_format=CURRENT_NOTE_FORMAT)


def render_series_note(title: str, *, years: str = "", genres: Iterable[str] = (), credits: Iterable[tuple[str, str]] = (),
                       publisher: str = "", lines: Iterable[str] = (), footer: Iterable[str] = ()) -> str:
    lines = [line for line in lines if line]
    facts = fact_lines(list(credits) + [("Publisher", publisher), ("Years", years)])
    body = join_blocks(f"# {title}", facts, ("## Albums\n\n" + "\n".join(lines)) if lines else "",
                       credit_footer(list(footer)))
    return render_note(_front(title, years, genres), body)


def render_grouping_note(title: str, *, years: str = "", intro: str = "", links: Iterable[str] = (),
                         footer: Iterable[str] = ()) -> str:
    return render_note(_front(title, years, links=links),
                       join_blocks(f"# {title}", intro, credit_footer(list(footer))))


def render_local_note(title: str, years: str = "") -> str:
    """The explicit minimal note from the folder name (a person asked for it; nothing was looked up or read)."""
    return render_note(_front(title, years), join_blocks(f"# {title}", credit_footer([LOCAL_ONLY_CREDIT])))
