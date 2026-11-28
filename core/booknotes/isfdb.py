"""
core/booknotes/isfdb.py

The local ISFDB database (Erlend's D28B, 2026-11-21: ISFDB first when the author is in it, Open Library for everyone
else). The file is built by epubredactor (Tools > ISFDB Database) from ISFDB's public backup; this program only reads it,
read-only, and never builds or changes it. Its path is a setting (core/booknotes/settings.py).

  IsfdbBooks(path)                 opens the file (IsfdbError when it is missing or not that kind of file)
  author_works(name)               the author's books (novels, collections, omnibuses), one per title, oldest first
  series_works(series, author)     the books of one series by that author, in ISFDB's series order

The schema (epubredactor core/isfdb_import.py): works(id, title, authors_text, year, series, series_num, series_parent,
language, ttype, variant_of) and works_fts(title, authors_text). Authors are 'Given Surname', several joined by '; '.
A translation or variant title points at its parent (variant_of) and is left out here: the parent is the book.

ISFDB's data is CC BY; the notes credit it (render.ISFDB_CREDIT).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from redactor_common.core.local_db import LocalDatabase, LocalDatabaseError, fts_match_string, normalize_words, open_cached

BOOK_TYPES = ("NOVEL", "COLLECTION", "OMNIBUS")  # an author's own books; anthologies are other people's stories
MAX_ROWS = 3000  # one author's works: Asimov has about 500 parents; the variants are many more
KIND = "an ISFDB lookup database built by epubredactor (Tools > ISFDB Database)"


class IsfdbError(LocalDatabaseError):
    """The ISFDB database is missing, unreadable or not the right kind of file."""


@dataclass
class Work:
    title: str
    year: str = ""
    series: str = ""
    number: str = ""
    kind: str = ""  # NOVEL, COLLECTION, OMNIBUS

    def sort_number(self) -> float:
        try:
            return float(self.number)
        except ValueError:
            return 1e9


class _Database(LocalDatabase):
    def __init__(self, path: str):
        super().__init__(path, ("works",), KIND, IsfdbError)
        self.has_fts = self.has_table("works_fts")


def split_authors(text: str) -> list[str]:
    return [a.strip() for a in re.split(r";|&", text or "") if a.strip()]


def same_name(a: str, b: str) -> bool:
    """'Iain M. Banks' and 'Iain M Banks' are the same name; 'Iain Banks' is not (ISFDB keeps them apart)."""
    return bool(a) and normalize_words(a) == normalize_words(b)


def _year(value) -> str:
    text = str(value or "")
    return text[:4] if text[:4].isdigit() and text[:4] != "0000" else ""


class IsfdbBooks:
    def __init__(self, path: str):
        self.db = open_cached(path, _Database)
        if not self.db.has_fts:
            raise IsfdbError("This ISFDB database has no full-text index: rebuild it in epubredactor (Tools > ISFDB Database).")

    def _rows(self, author: str, title_words: str = "") -> list[tuple]:
        author_match = fts_match_string(author, prefix=False)
        if not author_match:
            return []
        match = "{authors_text} : (" + author_match + ")"
        if title_words:
            title_match = fts_match_string(title_words, prefix=False)
            if not title_match:
                return []
            match += " AND {title} : (" + title_match + ")"
        marks = ",".join("?" * len(BOOK_TYPES))
        return self.db.query(
            "select w.title, w.year, w.series, w.series_num, w.ttype, w.authors_text from works_fts "
            "join works w on w.id = works_fts.rowid "
            f"where works_fts match ? and w.ttype in ({marks}) and (w.variant_of is null or w.variant_of = 0) limit ?",
            (match, *BOOK_TYPES, MAX_ROWS))

    def _works(self, rows: list[tuple], author: str) -> list[Work]:
        seen: set[str] = set()
        out: list[Work] = []
        for title, year, series, number, kind, authors in rows:
            if not any(same_name(author, a) for a in split_authors(authors)):
                continue  # the words matched, the person did not ('Iain Banks' for 'Iain M. Banks')
            key = normalize_words(title or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(Work(str(title).strip(), _year(year), str(series or "").strip(), str(number or "").strip(), str(kind or "")))
        return out

    def author_works(self, author: str) -> list[Work]:
        """The author's books, oldest first (a book with no year last)."""
        works = self._works(self._rows(author), author)
        return sorted(works, key=lambda w: (w.year or "9999", w.title.casefold()))

    def series_works(self, series: str, author: str) -> list[Work]:
        """The author's books in `series` (the name compared without case and punctuation), in series order."""
        wanted = normalize_words(series)
        works = [w for w in self.author_works(author) if wanted and normalize_words(w.series) == wanted]
        return sorted(works, key=lambda w: (w.sort_number(), w.year or "9999", w.title.casefold()))


def database_problem(path: str) -> str:
    """'' when the file at `path` can be used, else a plain sentence why not."""
    if not path:
        return "no ISFDB database file is set"
    try:
        IsfdbBooks(path)
    except LocalDatabaseError as exc:
        return str(exc)
    return ""
