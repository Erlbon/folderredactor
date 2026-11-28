"""
core/booknotes/render.py

The texts of the book notes (Erlend's D27, D29, D31, 2026-11-21). Pure: the same inputs always give the same note. The
writing itself (never overwriting, status: draft) is redactor_common's core/notes.py.

  author.md   front matter (title, years, genres, links), the Wikipedia introduction, "## Books": the series first, each
              under "### <series>" in series order, then "### Other books" by year; plain '- Title (Year)' lines (no links,
              nothing about what the library holds: Pluteus marks that itself)
  series.md   front matter, a short description, "## Books" in reading order ('- 1. Title (Year)')
  about.md    (a genre) front matter, a short paragraph on the genre
"""

from __future__ import annotations

from typing import Iterable

from core.version import APP_VERSION
from redactor_common.core.note_text import credit_footer, fact_lines, join_blocks
from redactor_common.core.notes import NoteFrontMatter, render_note

CURRENT_NOTE_FORMAT = 2  # the stamped shape (redactor_common core/notes.py); bump when a change is worth a refresh
ISFDB_CREDIT = "Book lists from the [ISFDB](https://www.isfdb.org/) (CC BY)"
LOCAL_ONLY_CREDIT = "Built from the folder only, no online source"
LOCAL_BOOKS_CREDIT = "Reading order from the books in the folder"


def generator_text() -> str:
    return f"folderredactor {APP_VERSION}"


def book_line(title: str, year: str = "", number: str = "") -> str:
    head = f"{number}. " if number else ""
    return f"- {head}{title}" + (f" ({year})" if year else "")


def _front(title: str, years: str = "", genres: Iterable[str] = (), links: Iterable[str] = ()) -> NoteFrontMatter:
    return NoteFrontMatter(title=title, years=years, genres=[g.lower() for g in genres if g], links=[u for u in links if u],
                           generator=generator_text(), note_format=CURRENT_NOTE_FORMAT)


def render_author_note(name: str, *, years: str = "", genres: Iterable[str] = (), intro: str = "",
                       groups: Iterable[tuple[str, list[str]]] = (), links: Iterable[str] = (),
                       footer: Iterable[str] = ()) -> str:
    """`groups` are (heading, book lines): one per series, then 'Other books'. A single group with no heading is a flat
    list (Open Library knows no series)."""
    parts: list[str] = []
    for heading, lines in groups:
        if lines:
            parts.append((f"### {heading}\n\n" if heading else "") + "\n".join(lines))
    books = ("## Books\n\n" + "\n\n".join(parts)) if parts else ""
    body = join_blocks(f"# {name}", intro, books, credit_footer(list(footer)))
    return render_note(_front(name, years, genres, links), body)


def render_series_note(title: str, *, author: str = "", intro: str = "", lines: Iterable[str] = (),
                       links: Iterable[str] = (), footer: Iterable[str] = ()) -> str:
    lines = list(lines)
    body = join_blocks(f"# {title}", intro, fact_lines([("Author", author)]),
                       ("## Books\n\n" + "\n".join(lines)) if lines else "", credit_footer(list(footer)))
    return render_note(_front(title, links=links), body)


def render_genre_note(title: str, *, intro: str = "", links: Iterable[str] = (), footer: Iterable[str] = ()) -> str:
    return render_note(_front(title, links=links), join_blocks(f"# {title}", intro, credit_footer(list(footer))))


def render_local_note(title: str) -> str:
    """The explicit minimal note from the folder name (a person asked for it; nothing was looked up)."""
    return render_note(_front(title), join_blocks(f"# {title}", credit_footer([LOCAL_ONLY_CREDIT])))
