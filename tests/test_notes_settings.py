"""What Create Notes remembers (core/notes_settings.py for every media type, core/video/settings.py for video), its
Preferences switches, Tools > Clear Lookup Cache and the lookup cache's place."""

import pytest
from PyQt6.QtWidgets import QMessageBox

from core import notes_settings, settings
from core.video import settings as video_settings


def test_the_defaults_are_both_kinds_subfolders_cache_and_wikipedia_on():
    assert video_settings.kinds() == ("series", "movie")
    assert notes_settings.include_subfolders() and notes_settings.cache_enabled() and notes_settings.wikipedia_enabled()
    assert notes_settings.last_folder() == "" and notes_settings.dialog_size() == ""


def test_the_choices_round_trip_through_the_settings_file():
    video_settings.set_kinds(["movie"])
    notes_settings.set_include_subfolders(False)
    notes_settings.set_cache_enabled(False)
    notes_settings.set_wikipedia_enabled(False)
    notes_settings.set_last_folder("D:\\Films")
    notes_settings.set_dialog_size("1200x800")
    assert video_settings.kinds() == ("movie",) and not notes_settings.include_subfolders()
    assert not notes_settings.cache_enabled() and not notes_settings.wikipedia_enabled()
    assert notes_settings.last_folder() == "D:\\Films" and notes_settings.dialog_size() == "1200x800"
    assert settings.get_setting("notes", "cache", "") == "0" and settings.get_setting("notes.video", "kinds", "") == "movie"


@pytest.mark.parametrize("text,expected", [
    ("series", ("series",)), ("movie", ("movie",)), ("both", ("series", "movie")), ("movie,series", ("series", "movie")),
    ("films", ("movie",)), ("", ("series", "movie")), ("nonsense", ("series", "movie")), (["movie"], ("movie",)),
])
def test_kinds_are_read_forgivingly_and_always_in_the_same_order(text, expected):
    assert video_settings.parse_kinds(text) == expected
    assert video_settings.kinds_text(text) == ",".join(expected)


def test_a_garbled_flag_means_the_default():
    settings.set_setting("notes", "cache", "maybe")
    assert notes_settings.cache_enabled() is True  # not one of the off words: the default (on)
    settings.set_setting("notes", "cache", "off")
    assert notes_settings.cache_enabled() is False


def test_the_cache_lives_next_to_the_settings_file_never_in_a_library(app_files, monkeypatch):
    from redactor_common.core import notes_cache as shared

    assert notes_settings.cache_path() == app_files / notes_settings.CACHE_FILE_NAME
    monkeypatch.setattr(shared, "_default", None)
    cache = notes_settings.default_cache(True)
    cache.put("k", b'"v"')
    assert (app_files / notes_settings.CACHE_FILE_NAME).is_file() and notes_settings.clear_cache() == 1
    assert notes_settings.default_cache(False) is None
    cache.close()
    monkeypatch.setattr(shared, "_default", None)


def test_the_preferences_switches_save_on_ok(qapp):
    from gui.preferences_dialog import PreferencesDialog

    dlg = PreferencesDialog()
    assert dlg.notes_cache_check.isChecked() and dlg.notes_wikipedia_check.isChecked()
    dlg.notes_cache_check.setChecked(False)
    dlg.notes_wikipedia_check.setChecked(False)
    dlg._on_ok()
    assert not notes_settings.cache_enabled() and not notes_settings.wikipedia_enabled()
    dlg.deleteLater()


def test_clear_lookup_cache_says_what_it_removed(window, monkeypatch):
    from redactor_common.core import notes_cache as shared

    said = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: said.append(a[2]) or QMessageBox.StandardButton.Ok))
    monkeypatch.setattr(shared, "_default", None)
    window.actions_by_key["clear_lookup_cache"].trigger()
    assert "already empty" in said[-1]
    cache = notes_settings.default_cache(True)
    cache.put("k", b'"v"')
    window.actions_by_key["clear_lookup_cache"].trigger()
    assert "1 saved answer removed" in said[-1]
    cache.close()
    monkeypatch.setattr(shared, "_default", None)
