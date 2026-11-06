"""The name with its turned F, the version and changelog, the docs the exe bundles, the shared lookup clients set up
for this app, API Keys, History and Preferences."""

import re
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

from core import api_keys, history, settings
from core.version import APP_NAME, APP_VERSION

ROOT = Path(__file__).parent.parent


# --- name, version, docs ------------------------------------------------------------------------------------------


def test_the_name_has_the_turned_f_written_as_an_escape_in_the_code():
    assert APP_NAME == "The Ⅎolder Redactor" and APP_NAME[4] == "\N{TURNED CAPITAL F}"
    source = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    assert re.search(r'^APP_NAME = "The \\u2132older Redactor"', source, re.MULTILINE)


def test_the_title_bar_and_the_about_box_show_the_name(window, qapp):
    from redactor_common.gui.about_dialog import AboutDialog

    assert window.windowTitle() == f"{APP_NAME} ({APP_VERSION})"
    shown = []
    original_exec = AboutDialog.exec
    AboutDialog.exec = lambda self: shown.append(self.windowTitle()) or 0
    try:
        window._on_show_about()
    finally:
        AboutDialog.exec = original_exec
    assert shown == [f"About {APP_NAME}"]


def test_the_changelog_has_a_section_for_the_current_version():
    from redactor_common.core.release_notes import build_notes

    tag = "v" + APP_VERSION.replace("#", "-")
    assert build_notes((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), tag, None).strip()


def test_the_spec_bundles_the_files_the_window_opens():
    spec = (ROOT / "folderredactor.spec").read_text(encoding="utf-8")
    for name in ("ABOUT.md", "CHANGELOG.md", "CREDITS.md", "assets/icon.ico"):
        assert f'"{name}"' in spec and (ROOT / name).is_file(), name
    assert 'name="folderredactor"' in spec and "upx=False" in spec


def test_credits_carry_the_notices_the_sources_ask_for():
    from redactor_common.core.lookups.tmdb import TMDB_NOTICE

    credits = (ROOT / "CREDITS.md").read_text(encoding="utf-8")
    assert " ".join(TMDB_NOTICE.split()) in " ".join(credits.split())
    for source in ("MusicBrainz", "Discogs", "Wikipedia", "CC BY-SA" if "CC BY-SA" in credits else "Attribution-ShareAlike"):
        assert source in credits


# --- the shared lookup clients, set up for this app ---------------------------------------------------------------


def test_the_lookup_clients_use_this_apps_user_agent_and_key_store(fake_keyring):
    from redactor_common.core.lookups import discogs, musicbrainz, tmdb
    from redactor_common.core import secret_store

    assert "folderredactor" in musicbrainz.USER_AGENT and "folderredactor" in discogs.USER_AGENT
    assert discogs.SECRET_APP == api_keys.APP == "folderredactor"
    assert tmdb.get_api_key() is None and discogs.load_token() == ""
    secret_store.set_secret("folderredactor", "tmdb_api_key", "tmdb-key")
    secret_store.set_secret("folderredactor", "discogs_token", "discogs-token")
    assert tmdb.get_api_key() == "tmdb-key" and discogs.load_token() == "discogs-token"


def test_an_environment_variable_wins_over_the_store(monkeypatch):
    from redactor_common.core import secret_store

    secret_store.set_secret("folderredactor", "tmdb_api_key", "stored")
    monkeypatch.setenv("TMDB_API_KEY", "from-env")
    assert api_keys.get_key("tmdb") == "from-env"


def test_api_keys_dialog_saves_into_the_credential_store_only(qapp, fake_keyring, app_files):
    from gui.api_keys_dialog import ApiKeysDialog

    dialog = ApiKeysDialog()
    dialog.fields["discogs"].edit.setText("typed-token")
    dialog.fields["tmdb"].edit.setText("typed-key")
    dialog._save(None)
    assert {name: value for (_service, name), value in fake_keyring.data.items()} == {
        "discogs_token": "typed-token", "tmdb_api_key": "typed-key"}
    assert {service for service, _name in fake_keyring.data} == {"redactor/shared"}  # the family's shared keys (D25)
    settings_file = app_files / "folderredactor_settings.ini"
    assert not settings_file.exists() or "typed" not in settings_file.read_text(encoding="utf-8")


# --- History --------------------------------------------------------------------------------------------------------


def test_history_is_off_by_default_and_writes_nothing(journal):
    assert not history.history_enabled()
    assert journal.begin("x.md", "note", {"text": ("", "new")}) is None
    assert not Path(journal.path).exists()


def test_history_lives_next_to_the_settings_never_in_a_library(app_files):
    history.set_journal(None)
    assert Path(history.journal_path()).parent == app_files
    assert Path(history.notes_backup_base()) == app_files


def test_tools_history_asks_before_turning_recording_on(window, monkeypatch):
    from redactor_common.gui import history_dialog

    opened = []
    monkeypatch.setattr(history_dialog.HistoryDialog, "exec", lambda self: opened.append(self.windowTitle()) or 0)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    window._on_open_history()
    assert opened == [] and not history.history_enabled()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._on_open_history()
    assert opened == ["History"] and history.history_enabled()


def test_preferences_turns_history_on_and_deletes_it(qapp, monkeypatch, journal):
    from gui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog()
    dialog.history_check.setChecked(True)
    dialog._on_ok()
    assert history.history_enabled()
    journal.begin("x.md", "note", {"text": ("", "new")})
    assert Path(journal.path).exists()
    trashed = []
    monkeypatch.setattr(history, "delete_history", lambda trash=None: trashed.append(journal.path) or "")
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    PreferencesDialog()._on_delete_history()
    assert trashed == [journal.path]


def test_delete_history_moves_the_journal_to_the_bin(journal):
    history.set_history_enabled(True)
    journal.begin("x.md", "note", {"text": ("", "new")})
    moved = []
    assert history.delete_history(trash=moved.append) == ""
    assert moved == [journal.path]


def test_preferences_switches_the_daily_update_check(qapp):
    from gui.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog()
    assert not dialog.updates_check.isChecked()
    dialog.updates_check.setChecked(True)
    dialog._on_ok()
    assert PreferencesDialog().updates_check.isChecked()


# --- settings -------------------------------------------------------------------------------------------------------


def test_settings_round_trip_and_a_percent_sign_is_kept(app_files):
    settings.set_setting("notes", "pattern", "%artist% - 100%")
    assert settings.get_setting("notes", "pattern") == "%artist% - 100%"
    settings.remove_setting("notes", "pattern")
    assert settings.get_setting("notes", "pattern", "gone") == "gone"
    assert settings.CONFIG_PATH.parent == app_files
