"""
core/history.py

The operations journal (redactor_common.core.journal) for this app, shown in Tools > History: every folder note it
writes (and, with the clean-up, every folder or file rename) is recorded, so it can be undone after the app was
closed. The journal file lives next to the settings, never in a library.

Opt-in, off by default (the family rule: no logging without a request): history_enabled() / set_history_enabled();
while off nothing is written.

What this module adds to the shared journal:
  get_journal()        the process-wide journal, `folderredactor_journal.jsonl` next to folderredactor_settings.ini
  note_undo_handlers() what Tools > History needs to undo a written or refreshed note
  apply_restore(...)   the History dialog's field restore: this app changes no tags, so there is nothing to restore
  delete_history()     the journal and the kept text of refreshed notes to the Recycle Bin

Qt-free.
"""

from __future__ import annotations

import os
import threading
from typing import Mapping, Optional

from redactor_common.core.journal import Journal, default_journal_path

from core import settings
from core.app_paths import APP_SLUG

SETTINGS_SECTION = "history"
SETTINGS_KEY = "enabled"
_TRUE = frozenset({"1", "true", "yes", "on"})

_lock = threading.Lock()
_journal: Optional[Journal] = None


def history_enabled() -> bool:
    """Whether changes are recorded ([history] enabled in the settings). A missing or garbled value, or an
    unreadable settings file, means off."""
    try:
        return settings.get_setting(SETTINGS_SECTION, SETTINGS_KEY, "").strip().lower() in _TRUE
    except Exception:  # noqa: BLE001 -- a broken settings file must not break a write
        return False


def set_history_enabled(enabled: bool) -> None:
    settings.set_setting(SETTINGS_SECTION, SETTINGS_KEY, "true" if enabled else "false")


class GatedJournal(Journal):
    """A Journal that writes nothing while history is off (reading still works, for a journal kept from when it
    was on)."""

    def begin(self, *args, **kwargs):
        return super().begin(*args, **kwargs) if history_enabled() else None

    def mark_restored(self, entry_id, restore_id):
        if history_enabled():
            super().mark_restored(entry_id, restore_id)

    def record_moves(self, pairs):
        if history_enabled():
            super().record_moves(pairs)


def journal_path() -> str:
    """`folderredactor_journal.jsonl` next to folderredactor_settings.ini."""
    return default_journal_path(APP_SLUG, os.path.dirname(os.path.abspath(os.fspath(settings.CONFIG_PATH))))


def get_journal() -> Journal:
    """The process-wide journal (a GatedJournal), created on first use; creating it writes nothing."""
    global _journal
    with _lock:
        if _journal is None:
            _journal = GatedJournal(journal_path())
        return _journal


def set_journal(journal: Optional[Journal]) -> None:
    """Replaces the process-wide journal (tests point it at tmp_path); None makes the next get_journal() create the
    default one again."""
    global _journal
    with _lock:
        _journal = journal


def journal_exists() -> bool:
    return os.path.isfile(get_journal().path)


def notes_backup_base() -> str:
    """The folder that holds `notes_backup/` (the text a refreshed note replaced): the journal's folder, next to the
    settings; never a library folder."""
    return os.path.dirname(os.path.abspath(get_journal().path))


def note_undo_handlers() -> dict:
    """kind -> handler(entry) -> (ok, message) for a created ('note') and a refreshed ('note-update') note."""
    from redactor_common.core.notes_model import KIND_NOTE, KIND_NOTE_UPDATE, make_note_undo_handler  # noqa: PLC0415

    handler = make_note_undo_handler(get_journal(), notes_backup_base())
    return {KIND_NOTE: handler, KIND_NOTE_UPDATE: handler}


def apply_restore(path: str, values: Mapping[str, str]) -> str:
    """The History dialog's field restore. This app writes no tags, so no entry of its own has fields to restore;
    notes are undone through note_undo_handlers()."""
    return "this program changes no tags, so there is nothing to restore here"


def delete_history(trash=None) -> str:
    """Moves the journal file (and a leftover prune temp file, and the kept text of refreshed notes) to the Recycle
    Bin (`trash`, injectable for tests). Returns "" or the problem."""
    if trash is None:
        from redactor_common.core.trash import move_to_trash as trash  # noqa: PLC0415
    path = get_journal().path
    try:
        from redactor_common.core.notes_model import backup_folder  # noqa: PLC0415

        for candidate in (path, path + ".tmp", backup_folder(notes_backup_base())):
            if os.path.exists(candidate):
                trash(candidate)
    except Exception as exc:  # noqa: BLE001 -- TrashError or OSError: reported, not raised
        return str(exc)
    return ""
