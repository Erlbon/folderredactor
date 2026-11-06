"""
core/old_apps.py

Bringing over what mp3redactor and videoredactor knew about notes (plan step 10, decision D5). Qt-free.

  found_keys()                 the keys this app uses (Discogs, TMDB) that are still only in an app's OWN credential entry
                               (mp3redactor's, videoredactor's, or this app's from before the shared store), not in the
                               family's shared one: found by their entry NAMES, wherever the exes live
  copy_keys(found)             shares them with every Redactor (redactor_common's share_keys; only when the person said
                               yes, never silent; the old entries stay for the apps that do not read the shared keys yet)
  import_folder(folder)        an old app's folder: its notes settings (mp3redactor_settings.ini / videoredactor_settings.ini)
                               and its lookup cache, merged into this app's; returns what was done, in plain lines

The settings and the cache sit next to each old exe, and the family has no fixed install path, so they are only read from a
folder the person points at (File > Import from mp3redactor or videoredactor). An import FILLS what is not set here yet:
it never overwrites a choice made in this app. The troubleshooting-log switch is not carried over (logging is opt-in, here
too).
"""

from __future__ import annotations

import configparser
import os
import sqlite3
from pathlib import Path

from core import notes_settings, settings
from core.api_keys import APP, KEYS
from redactor_common.core import secret_store

MP3, VIDEO = "mp3redactor", "videoredactor"
SETTINGS_FILES = {MP3: "mp3redactor_settings.ini", VIDEO: "videoredactor_settings.ini"}
CACHE_FILES = {MP3: "mp3redactor_notes_cache.sqlite", VIDEO: "videoredactor_notes_cache.sqlite"}
_TRUE = frozenset({"1", "true", "yes", "on"})

# mp3redactor kept its notes choices in [general] as notes_*; videoredactor in [notes]. old key -> (our section, our key, kind)
MP3_SETTINGS = {
    "notes_kinds": ("notes.music", "kinds", "text"),
    "notes_discogs_always": ("notes.music", "discogs_always", "flag"),
    "notes_skip_singles": ("notes.music", "skip_singles", "flag"),
    "notes_norwegian_numbers": ("notes.music", "norwegian_numbers", "flag"),
    "notes_cache_enabled": ("notes", "cache", "flag"),
    "notes_last_folder": ("notes", "last_folder", "text"),
    "notes_dialog_size": ("notes", "dialog_size", "text"),
}
VIDEO_SETTINGS = {
    "kinds": ("notes.video", "kinds", "text"),
    "cache": ("notes", "cache", "flag"),
    "wikipedia": ("notes", "wikipedia", "flag"),
    "last_folder": ("notes", "last_folder", "text"),
    "dialog_size": ("notes", "dialog_size", "text"),
}


def found_keys() -> list:
    """The keys this app uses that are in some app's own entry but not yet shared (secret_store.UnsharedKey: .label,
    .app, never the value in a repr). An unreadable store has nothing to offer."""
    try:
        found = secret_store.unshared_keys([name for name, _env, _label in KEYS.values()])
        # The key this app uses now wins over another app's copy: sharing must never quietly change it here.
        out = []
        for key in found:
            own = secret_store.get_secret(APP, key.name).strip()
            out.append(secret_store.UnsharedKey(key.name, key.label, APP, own) if own else key)
        return out
    except Exception:  # noqa: BLE001
        return []


def copy_keys(found: list) -> list[str]:
    """Shares them with every Redactor; returns the plain-language problems (e.g. no credential store and no consent to
    the fallback file), never a value."""
    try:
        return secret_store.share_keys(found)
    except Exception as exc:  # noqa: BLE001
        return [f"the keys could not be shared ({type(exc).__name__})"]


def detect(folder: str | os.PathLike) -> list[str]:
    """The old apps whose settings file or lookup cache is in `folder`."""
    folder = Path(folder)
    return [app for app in (MP3, VIDEO)
            if (folder / SETTINGS_FILES[app]).is_file() or (folder / CACHE_FILES[app]).is_file()]


def _import_settings(path: Path, section: str, mapping: dict) -> int:
    old = configparser.ConfigParser(interpolation=None)
    old.read(path, encoding="utf-8")
    if not old.has_section(section):
        return 0
    done = 0
    for old_key, (our_section, our_key, kind) in mapping.items():
        value = old.get(section, old_key, fallback="").strip()
        if not value or settings.get_setting(our_section, our_key, "").strip():
            continue  # nothing there, or chosen here already: never overwritten
        if kind == "flag":
            value = "1" if value.lower() in _TRUE else "0"
        settings.set_setting(our_section, our_key, value)
        done += 1
    return done


def _merge_cache(source: Path) -> int:
    """Copies the old cache's answers that this app's cache does not have (same table: redactor_common's ResponseCache)."""
    from redactor_common.core.notes_cache import ResponseCache

    target = notes_settings.cache_path()
    ResponseCache(target).close()  # makes sure the file and its table exist
    with sqlite3.connect(str(target)) as db:
        before = db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        db.execute("ATTACH DATABASE ? AS old", (str(source),))
        try:
            db.execute("INSERT OR IGNORE INTO cache (key, status, body, expires, used, size) "
                       "SELECT key, status, body, expires, used, size FROM old.cache")
            db.commit()
        finally:
            db.execute("DETACH DATABASE old")
        return db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] - before


def import_folder(folder: str | os.PathLike) -> list[str]:
    """Imports the notes settings and the lookup cache of the old app(s) in `folder`; returns what was done."""
    folder = Path(folder)
    apps = detect(folder)
    if not apps:
        return [f"No mp3redactor or videoredactor settings or lookup cache in {folder}."]
    lines = []
    for app in apps:
        ini = folder / SETTINGS_FILES[app]
        if ini.is_file():
            try:
                n = _import_settings(ini, "general", MP3_SETTINGS) if app == MP3 else _import_settings(ini, "notes", VIDEO_SETTINGS)
                lines.append(f"{app}: {n} notes setting(s) taken over" if n else
                             f"{app}: no notes settings to take over (none, or already set here)")
            except (OSError, configparser.Error) as exc:
                lines.append(f"{app}: its settings could not be read ({exc})")
        cache = folder / CACHE_FILES[app]
        if cache.is_file():
            try:
                lines.append(f"{app}: {_merge_cache(cache)} saved lookup answer(s) added to the cache")
            except sqlite3.Error as exc:
                lines.append(f"{app}: its lookup cache could not be read ({exc})")
    return lines
