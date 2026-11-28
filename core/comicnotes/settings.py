"""
core/comicnotes/settings.py

What comics notes remember in the settings file, beside the choices every media type shares (core/notes_settings.py):

  [notes.comics] kinds    'series,grouping' (which folders Look Up makes a note for)
"""

from __future__ import annotations

from core import settings
from core.comics import ALL_KINDS

SECTION = "notes.comics"
_ALIASES = {"all": ALL_KINDS, "both": ALL_KINDS, "groupings": ("grouping",), "about": ("grouping",),
            "publisher": ("grouping",), "publishers": ("grouping",)}


def parse_kinds(text) -> tuple[str, ...]:
    """The kinds named in `text` ('series', 'grouping', 'all', a comma list, or a list), in the order series, grouping;
    all of them when the text is empty or unreadable."""
    words = [str(w) for w in text] if isinstance(text, (list, tuple, set, frozenset)) else str(text or "").replace(";", ",").split(",")
    found: set[str] = set()
    for word in (w.strip().lower() for w in words):
        if word in ALL_KINDS:
            found.add(word)
        elif word in _ALIASES:
            found.update(_ALIASES[word])
    return tuple(k for k in ALL_KINDS if k in found) or ALL_KINDS


def kinds() -> tuple[str, ...]:
    try:
        return parse_kinds(settings.get_setting(SECTION, "kinds", ""))
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the defaults
        return ALL_KINDS


def set_kinds(kinds_value) -> None:
    settings.set_setting(SECTION, "kinds", ",".join(parse_kinds(kinds_value)))
