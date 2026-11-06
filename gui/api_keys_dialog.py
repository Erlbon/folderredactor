"""
gui/api_keys_dialog.py

Tools > API Keys: the Discogs token and the TMDB API key the folder notes look things up with: the Redactor family's
shared keys (core/api_keys.py), in the OS credential store, never in the settings file. Each row is a redactor_common
SecretField(shared=True): a masked edit that never shows the stored value (empty = keep it), a Remove button, and a
label naming where the key comes from and which other Redactors use it, including "taken from an environment
variable", which wins over anything entered here. Saving changes the key for every Redactor that uses it.

With no usable credential store saving raises SecretStoreUnavailable; the user is asked whether to use an
UNENCRYPTED file instead, and only a yes is remembered.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from core import api_keys
from redactor_common.core.lookups.discogs import TOKEN_HELP_URL
from redactor_common.gui.owned_dialog import OwnedDialog
from redactor_common.gui.secret_field import SecretField
from redactor_common.gui.secret_prompts import save_with_fallback_prompt

TMDB_HELP_URL = "https://www.themoviedb.org/settings/api"


class ApiKeysDialog(OwnedDialog):
    """Saves on Save; nothing elsewhere needs refreshing, since a key is only read when a lookup runs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Keys")
        self.resize(560, 300)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Your own keys for the lookup services the folder notes use: a Discogs token (music) and a TMDB API key "
            f'(films and series). Both are free: Discogs under <a href="{TOKEN_HELP_URL}">Settings &gt; '
            f'Developers</a>, TMDB under <a href="{TMDB_HELP_URL}">Settings &gt; API</a>. MusicBrainz and Wikipedia '
            "need no key. Keys are kept in your system's credential store, not in a settings file, and are shared by "
            "the Redactors: a key saved here is the key for every Redactor that uses it."
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.fields: dict[str, SecretField] = {}
        for key_id, (name, env_var, label) in api_keys.KEYS.items():
            field = SecretField(api_keys.APP, name, env_var=env_var, shared=True)
            self.fields[key_id] = field
            form.addRow(f"{label}:", field)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save)
        buttons.addWidget(self.save_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

    def _save(self, allow_unencrypted_fallback) -> None:
        for field in self.fields.values():
            field.apply(allow_unencrypted_fallback)

    def _on_save(self) -> None:
        remember = api_keys.apply_fallback_preference()
        # Declined or failed: stay open with what was typed; nothing is lost.
        if save_with_fallback_prompt(self, self._save, remember, noun="API keys"):
            self.accept()
