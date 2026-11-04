"""
core/app_paths.py

Where this app's own files live (settings ini, crash log, History journal, update switch), via
redactor_common.core.app_paths: next to the exe, or the project folder when running from source. Never inside a
library: the only thing this app writes into a library is a folder note (`.md`).
"""

from __future__ import annotations

from pathlib import Path

from redactor_common.core import app_paths as _shared

APP_SLUG = "folderredactor"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def base_dir() -> Path:
    return _shared.base_dir(PROJECT_ROOT)


def asset_path(relative: str) -> Path:
    return _shared.asset_path(relative, PROJECT_ROOT)


def settings_ini_path() -> Path:
    return _shared.settings_ini_path(APP_SLUG, PROJECT_ROOT)


def crash_log_path() -> Path:
    return _shared.crash_log_path(APP_SLUG, PROJECT_ROOT)


def updates_json_path() -> Path:
    """Help > Check for Updates' own small settings file (redactor_common.core.selfupdate.UpdateSettings)."""
    return base_dir() / f"{APP_SLUG}_updates.json"
