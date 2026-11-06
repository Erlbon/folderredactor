"""
core/notes_settings.py

What Notes > Create Notes remembers for every media type (the settings file next to the exe) and where its lookup
cache lives. Small on purpose: the window, the command line and the tests all go through these functions. What one
media type adds is its own module (core/video/settings.py: [notes.video]).

  [notes] last_folder    the folder the person used last time
  [notes] media          'music' / 'video': the kind of library used last time (when a library's files cannot tell)
  [notes] include_subfolders  '1' (default) / '0': the folders below the chosen one get notes too
  [notes] cache         '1' (default) / '0': keep answers of earlier lookups on disk
  [notes] dialog_size    'WxH' of the review page
  [notes] wikipedia      '1' (default) / '0': a Wikipedia introduction in the notes
  [notes] debug_log      '0' (default) / '1': the troubleshooting log of the review list (core/notes_debug.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core import settings
from redactor_common.core import notes_cache as shared_cache

SECTION = "notes"
CACHE_FILE_NAME = "folderredactor_notes_cache.sqlite"
_FALSE = frozenset({"0", "false", "no", "off"})


def _get(key: str, default: str = "") -> str:
    try:
        return settings.get_setting(SECTION, key, default)
    except Exception:  # noqa: BLE001 -- an unreadable settings file means the defaults
        return default


def _flag(key: str, default: bool = True) -> bool:
    value = _get(key, "1" if default else "0").strip().lower()
    return default if not value else value not in _FALSE


def last_folder() -> str:
    return _get("last_folder")


def set_last_folder(folder: str) -> None:
    settings.set_setting(SECTION, "last_folder", folder)


MEDIA = ("music", "video")


def last_media() -> str:
    """'music' or 'video': the kind of library notes were made for last time ([notes] media; '' = never)."""
    value = _get("media").strip().lower()
    return value if value in MEDIA else ""


def set_last_media(media: str) -> None:
    if media in MEDIA:
        settings.set_setting(SECTION, "media", media)


def include_subfolders() -> bool:
    return _flag("include_subfolders")


def set_include_subfolders(enabled: bool) -> None:
    settings.set_setting(SECTION, "include_subfolders", "1" if enabled else "0")


def cache_enabled() -> bool:
    return _flag("cache")


def set_cache_enabled(enabled: bool) -> None:
    settings.set_setting(SECTION, "cache", "1" if enabled else "0")


def wikipedia_enabled() -> bool:
    return _flag("wikipedia")


def set_wikipedia_enabled(enabled: bool) -> None:
    settings.set_setting(SECTION, "wikipedia", "1" if enabled else "0")


def debug_log_enabled() -> bool:
    return _flag("debug_log", default=False)


def set_debug_log_enabled(enabled: bool) -> None:
    settings.set_setting(SECTION, "debug_log", "1" if enabled else "0")


def dialog_size() -> str:
    return _get("dialog_size")


def set_dialog_size(text: str) -> None:
    settings.set_setting(SECTION, "dialog_size", text)


# ---- the cache -------------------------------------------------------------------------------------------------------

def cache_path() -> Path:
    """Next to the settings file (never in a library folder). One cache for every media type: its keys start with the
    service ('tmdb|...', 'wiki|...')."""
    return Path(settings.CONFIG_PATH).parent / CACHE_FILE_NAME


def default_cache(enabled: Optional[bool] = None):
    """The process-wide lookup cache, or None when the setting (or `enabled`) is off."""
    return shared_cache.default_cache(cache_path(), cache_enabled() if enabled is None else enabled)


def clear_cache() -> int:
    """Tools > Clear Lookup Cache: the entries removed (0 when there is none)."""
    return shared_cache.clear_default_cache(cache_path())
