"""
gui/preferences_dialog.py

Tools > Preferences. For now one page's worth: History (record what this program writes, off by default, with a
button that deletes what was recorded) and the daily update check. The notes and clean-up settings join with their
steps.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QDialogButtonBox, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from core import app_paths, history
from redactor_common.core.selfupdate import KEY_CHECK_FOR_UPDATES, UpdateSettings
from redactor_common.gui.owned_dialog import OwnedDialog


class PreferencesDialog(OwnedDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(520, 260)
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

    def _on_ok(self) -> None:
        if self.history_check.isChecked() != history.history_enabled():
            history.set_history_enabled(self.history_check.isChecked())
        if self.updates_check.isChecked() != self.update_settings.enabled:
            self.update_settings.update(**{KEY_CHECK_FOR_UPDATES: self.updates_check.isChecked()})
        self.accept()
