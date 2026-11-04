"""
core/settings.py

The app's settings: one `folderredactor_settings.ini` next to the exe (core.app_paths.settings_ini_path()), never in
a library. Sections per job ("[notes.music]", "[notes.video]", "[cleanup]" ...) are added by the steps that need
them; this module is only the plumbing.

interpolation=None: a '%' in a saved value (a pattern, a path) must not be read as configparser syntax. Writes go
through a temp file + os.replace, so a crash mid-write never leaves a half-written settings file.
"""

from __future__ import annotations

import configparser
import os
import time
from pathlib import Path

from core.app_paths import settings_ini_path

CONFIG_PATH: Path = settings_ini_path()


def load_config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    if CONFIG_PATH.exists():
        parser.read(CONFIG_PATH, encoding="utf-8")
    return parser


def save_config(parser: configparser.ConfigParser) -> None:
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            parser.write(handle)
        # Windows: os.replace can fail for a moment when an antivirus or indexer has the target open.
        for attempt in range(10):
            try:
                os.replace(tmp, CONFIG_PATH)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def get_setting(section: str, key: str, default: str = "") -> str:
    return load_config().get(section, key, fallback=default)


def set_setting(section: str, key: str, value: str) -> None:
    parser = load_config()
    if not parser.has_section(section):
        parser.add_section(section)
    parser.set(section, key, value)
    save_config(parser)


def remove_setting(section: str, key: str) -> None:
    parser = load_config()
    if parser.has_section(section) and parser.remove_option(section, key):
        if not parser.options(section):
            parser.remove_section(section)
        save_config(parser)


# --- File > Recent ------------------------------------------------------------------------------------------------

RECENT_SECTION = "recent"
RECENT_MAX = 10


def recent_folders() -> list[str]:
    """The library folders opened last, newest first (File > Recent)."""
    parser = load_config()
    if not parser.has_section(RECENT_SECTION):
        return []
    items = sorted(parser.items(RECENT_SECTION), key=lambda kv: kv[0])
    return [value for _key, value in items if value][:RECENT_MAX]


def add_recent_folder(folder: str) -> list[str]:
    """`folder` at the top of File > Recent (moved up when it is already there); returns the new list."""
    folder = os.path.normpath(folder)
    key = os.path.normcase(folder)
    folders = [folder] + [f for f in recent_folders() if os.path.normcase(os.path.normpath(f)) != key]
    _write_recent(folders[:RECENT_MAX])
    return folders[:RECENT_MAX]


def clear_recent_folders() -> None:
    _write_recent([])


def _write_recent(folders: list[str]) -> None:
    parser = load_config()
    if parser.has_section(RECENT_SECTION):
        parser.remove_section(RECENT_SECTION)
    if folders:
        parser.add_section(RECENT_SECTION)
        for index, folder in enumerate(folders):
            parser.set(RECENT_SECTION, f"{index:02d}", folder)
    save_config(parser)
