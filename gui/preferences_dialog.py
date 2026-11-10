"""
gui/preferences_dialog.py

Tools > Preferences. For now one page's worth: History (record what this program writes, off by default, with a
button that deletes what was recorded), Look Up (keep the lookup answers on disk, a Wikipedia introduction) and
the daily update check. The clean-up settings join with their steps.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from core import app_paths, history, notes_debug, notes_settings
from core.music import settings as music_settings
from redactor_common.core.selfupdate import KEY_CHECK_FOR_UPDATES, UpdateSettings
from redactor_common.gui.owned_dialog import OwnedDialog


class PreferencesDialog(OwnedDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(600, 480)
        layout = QVBoxLayout(self)

        box = QGroupBox("History")
        box_layout = QVBoxLayout(box)
        self.history_check = QCheckBox("Record the notes this program writes (Tools > History), so they can be undone")
        self.history_check.setChecked(history.history_enabled())
        box_layout.addWidget(self.history_check)
        note = QLabel("Off by default. The record is kept next to the program, never in a library.")
        note.setWordWrap(True)
        box_layout.addWidget(note)
        row = QHBoxLayout()
        self.delete_button = QPushButton("Delete History…")
        self.delete_button.setToolTip("Move everything recorded so far to the Recycle Bin")
        self.delete_button.clicked.connect(self._on_delete_history)
        row.addWidget(self.delete_button)
        row.addStretch()
        box_layout.addLayout(row)
        layout.addWidget(box)

        notes_box = QGroupBox("Look Up")
        notes_layout = QVBoxLayout(notes_box)
        self.notes_cache_check = QCheckBox("Keep the answers of earlier lookups, so a second run is quick")
        self.notes_cache_check.setToolTip("Kept next to the program, never in a library. Tools > Clear Lookup Cache "
                                          "forgets them.")
        self.notes_cache_check.setChecked(notes_settings.cache_enabled())
        notes_layout.addWidget(self.notes_cache_check)
        self.notes_wikipedia_check = QCheckBox("Start a note with the Wikipedia introduction, when the article is "
                                               "certainly the right one")
        self.notes_wikipedia_check.setChecked(notes_settings.wikipedia_enabled())
        notes_layout.addWidget(self.notes_wikipedia_check)
        debug_row = QHBoxLayout()
        self.notes_debug_check = QCheckBox("Log the review list for troubleshooting (off by default)")
        self.notes_debug_check.setToolTip("Only counts, scroll positions and folder names, next to the program. Never file "
                                          "contents or note text.")
        self.notes_debug_check.setChecked(notes_settings.debug_log_enabled())
        debug_row.addWidget(self.notes_debug_check)
        self.delete_debug_button = QPushButton("Delete Log")
        self.delete_debug_button.setEnabled(notes_debug.log_exists())
        self.delete_debug_button.clicked.connect(self._on_delete_debug_log)
        debug_row.addWidget(self.delete_debug_button)
        debug_row.addStretch()
        notes_layout.addLayout(debug_row)
        layout.addWidget(notes_box)

        music_box = QGroupBox("Look Up: music")
        music_layout = QVBoxLayout(music_box)
        self.discogs_always_check = QCheckBox("Ask Discogs for every artist (slower; off: only when MusicBrainz has no "
                                              "verified match)")
        self.discogs_always_check.setToolTip("Needs a Discogs token (Tools > API Keys).")
        self.discogs_always_check.setChecked(music_settings.discogs_always())
        music_layout.addWidget(self.discogs_always_check)
        self.skip_singles_check = QCheckBox("Leave the singles out of an artist's discography (faster)")
        self.skip_singles_check.setChecked(music_settings.skip_singles())
        music_layout.addWidget(self.skip_singles_check)
        self.norwegian_check = QCheckBox("Count the Norwegian number words en, to, tre, fire, fem, ni, ti as numbers "
                                         "when titles are compared")
        self.norwegian_check.setToolTip("Off by default: these are everyday English words too ('Fire', 'To', 'Ten').")
        self.norwegian_check.setChecked(music_settings.norwegian_numbers())
        music_layout.addWidget(self.norwegian_check)
        layout.addWidget(music_box)

        self.update_settings = UpdateSettings(app_paths.updates_json_path())
        self.updates_check = QCheckBox("Check for a new version once a day")
        self.updates_check.setToolTip("Asks GitHub at startup, at most once a day. Nothing about you or your files "
                                      "is sent.")
        self.updates_check.setChecked(self.update_settings.enabled)
        layout.addWidget(self.updates_check)

        layout.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_delete_history(self) -> None:
        answer = QMessageBox.question(
            self, "Delete History",
            "Move the recorded history to the Recycle Bin? Notes written so far can then no longer be undone from "
            "Tools > History.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        problem = history.delete_history()
        if problem:
            QMessageBox.warning(self, "Delete History", f"The history could not be deleted: {problem}")
        else:
            QMessageBox.information(self, "Delete History", "The history was moved to the Recycle Bin.")

    def _on_delete_debug_log(self) -> None:
        problem = notes_debug.delete_log()
        if problem:
            QMessageBox.warning(self, "Delete Log", problem)
        else:
            QMessageBox.information(self, "Delete Log", "The troubleshooting log was deleted.")
        self.delete_debug_button.setEnabled(notes_debug.log_exists())

    def _on_ok(self) -> None:
        if self.history_check.isChecked() != history.history_enabled():
            history.set_history_enabled(self.history_check.isChecked())
        if self.notes_cache_check.isChecked() != notes_settings.cache_enabled():
            notes_settings.set_cache_enabled(self.notes_cache_check.isChecked())
        if self.notes_wikipedia_check.isChecked() != notes_settings.wikipedia_enabled():
            notes_settings.set_wikipedia_enabled(self.notes_wikipedia_check.isChecked())
        if self.notes_debug_check.isChecked() != notes_settings.debug_log_enabled():
            notes_settings.set_debug_log_enabled(self.notes_debug_check.isChecked())
            notes_debug.set_enabled(self.notes_debug_check.isChecked())  # the running app follows at once
        for box, read, write in ((self.discogs_always_check, music_settings.discogs_always, music_settings.set_discogs_always),
                                 (self.skip_singles_check, music_settings.skip_singles, music_settings.set_skip_singles),
                                 (self.norwegian_check, music_settings.norwegian_numbers, music_settings.set_norwegian_numbers)):
            if box.isChecked() != read():
                write(box.isChecked())
        if self.updates_check.isChecked() != self.update_settings.enabled:
            self.update_settings.update(**{KEY_CHECK_FOR_UPDATES: self.updates_check.isChecked()})
        self.accept()
