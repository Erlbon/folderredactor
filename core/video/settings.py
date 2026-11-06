"""
core/video/settings.py

What video notes remember in the settings file, beside the choices every media type shares (core/notes_settings.py):

  [notes.video] kinds    'series,movie' (which folders get a note)
"""

from __future__ import annotations

from core import settings
from core.video.local import ALL_KINDS

SECTION = "notes.video"


def parse_kinds(text) -> tuple[str, ...]:
    """The kinds named in `text` ('series', 'movie', 'both', a comma list, or a list), in the order series, movie; both when
    the text is empty or unreadable."""
    words = [str(w) for w in text] if isinstance(text, (list, tuple, set, frozenset)) else str(text or "").replace(";", ",").split(",")
    found = set()
    for word in (w.strip().lower() for w in words):
        if word in ALL_KINDS:
            found.add(word)
        elif word in ("both", "all"):
            found.update(ALL_KINDS)
        elif word in ("film", "films", "movies"):
            found.add("movie")
    return tuple(k for k in ALL_KINDS if k in found) or ALL_KINDS


def kinds_text(kinds) -> str:
    return ",".join(parse_kinds(kinds))


def kinds() -> tuple[str, ...]:
    try:
        return parse_kinds(settings.get_setting(SECTION, "kinds", ""))
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the defaults
        return ALL_KINDS


def set_kinds(kinds_value) -> None:
    settings.set_setting(SECTION, "kinds", kinds_text(kinds_value))
