"""
core/booknotes/settings.py

What book notes remember in the settings file, beside the choices every media type shares (core/notes_settings.py):

  [notes.books] kinds    'author,series,genre' (which folders Look Up makes a note for)
  [notes.books] isfdb    the path of the ISFDB database epubredactor built (isfdb.db); empty = Open Library only
"""

from __future__ import annotations

from core import settings
from core.books import ALL_KINDS

SECTION = "notes.books"


def parse_kinds(text) -> tuple[str, ...]:
    """The kinds named in `text` ('author', 'series', 'genre', 'all', a comma list, or a list), in the order author,
    series, genre; all of them when the text is empty or unreadable."""
    words = [str(w) for w in text] if isinstance(text, (list, tuple, set, frozenset)) else str(text or "").replace(";", ",").split(",")
    found = set()
    for word in (w.strip().lower() for w in words):
        if word in ALL_KINDS:
            found.add(word)
        elif word in ("all", "both"):
            found.update(ALL_KINDS)
        elif word in ("authors", "genres", "about"):
            found.add({"authors": "author", "genres": "genre", "about": "genre"}[word])
    return tuple(k for k in ALL_KINDS if k in found) or ALL_KINDS


def kinds() -> tuple[str, ...]:
    try:
        return parse_kinds(settings.get_setting(SECTION, "kinds", ""))
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the defaults
        return ALL_KINDS


def set_kinds(kinds_value) -> None:
    settings.set_setting(SECTION, "kinds", ",".join(parse_kinds(kinds_value)))


def isfdb_path() -> str:
    try:
        return settings.get_setting(SECTION, "isfdb", "").strip()
    except Exception:  # noqa: BLE001
        return ""


def set_isfdb_path(path: str) -> None:
    settings.set_setting(SECTION, "isfdb", (path or "").strip())
