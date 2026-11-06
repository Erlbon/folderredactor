"""
core/music/settings.py

What music notes remember in the settings file, beside the choices every media type shares (core/notes_settings.py: the
last folder, the lookup cache switch, the Wikipedia switch). The engine's options are mp3redactor's Preferences > Create
Notes switches, with the same defaults:

  [notes.music] kinds              'artist' (the default), 'artist,album', 'artist,album,genre' ... (core/music/kinds.py)
  [notes.music] discogs_always     '0' (default): Discogs only when MusicBrainz has no verified match; '1': every artist
  [notes.music] skip_singles       '0' (default); '1': the singles are left out of an artist's discography (faster)
  [notes.music] norwegian_numbers  '0' (default); '1': en, to, tre, fire ... count as numbers when titles are compared

The window and the command line read them through engine_options(); a command-line flag wins for that run.
"""

from __future__ import annotations

from core import settings
from core.music.kinds import kinds_text, parse_kinds  # noqa: F401 -- kinds_text / parse_kinds: the window uses them from here

SECTION = "notes.music"
_TRUE = frozenset({"1", "true", "yes", "on"})


def _get(key: str) -> str:
    try:
        return settings.get_setting(SECTION, key, "")
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the defaults
        return ""


def _flag(key: str) -> bool:
    return _get(key).strip().lower() in _TRUE  # every switch here is off by default


def _set_flag(key: str, on: bool) -> None:
    settings.set_setting(SECTION, key, "1" if on else "0")


def kinds() -> tuple[str, ...]:
    """The kinds chosen last time; artist notes only when nothing (or nothing readable) is saved."""
    return parse_kinds(_get("kinds"))


def set_kinds(kinds_value) -> None:
    settings.set_setting(SECTION, "kinds", kinds_text(kinds_value))


def discogs_always() -> bool:
    return _flag("discogs_always")


def set_discogs_always(on: bool) -> None:
    _set_flag("discogs_always", on)


def skip_singles() -> bool:
    return _flag("skip_singles")


def set_skip_singles(on: bool) -> None:
    _set_flag("skip_singles", on)


def norwegian_numbers() -> bool:
    return _flag("norwegian_numbers")


def set_norwegian_numbers(on: bool) -> None:
    _set_flag("norwegian_numbers", on)


def engine_options() -> dict:
    """NotesEngine's keyword options from the settings: discogs_mode and singles."""
    return {"discogs_mode": "always" if discogs_always() else "fallback", "singles": not skip_singles()}


def apply_number_words() -> None:
    """The title normaliser follows the Norwegian-number-words switch (process-wide, like mp3redactor)."""
    from core.music.numbers import set_norwegian_numbers as fold

    fold(norwegian_numbers())
