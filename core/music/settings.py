"""
core/music/settings.py

What music notes remember in the settings file, beside the choices every media type shares (core/notes_settings.py: the
last folder, the lookup cache switch, the Wikipedia switch):

  [notes.music] kinds    'artist' (the default), 'artist,album', 'artist,album,genre' ... (core/music/kinds.py)

The engine's other options (Discogs always / fallback / never, singles in the discography, Norwegian number words) join
here with the music review page and the command line that set them (plan steps 9-10).
"""

from __future__ import annotations

from core import settings
from core.music.kinds import kinds_text, parse_kinds  # noqa: F401 -- kinds_text / parse_kinds: the window uses them from here

SECTION = "notes.music"


def kinds() -> tuple[str, ...]:
    """The kinds chosen last time; artist notes only when nothing (or nothing readable) is saved."""
    try:
        return parse_kinds(settings.get_setting(SECTION, "kinds", ""))
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the default
        return parse_kinds("")


def set_kinds(kinds_value) -> None:
    settings.set_setting(SECTION, "kinds", kinds_text(kinds_value))
