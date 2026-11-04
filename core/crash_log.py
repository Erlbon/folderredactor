"""
core/crash_log.py

Crash logging via redactor_common.core.crash_log; the log lives next to the app (core.app_paths.crash_log_path()).
"""

from __future__ import annotations

from redactor_common.core import crash_log as _shared

from core.app_paths import crash_log_path


def log_path() -> str:
    return str(crash_log_path())


def install(also_call=None) -> None:
    _shared.install(log_path(), also_call=also_call)
