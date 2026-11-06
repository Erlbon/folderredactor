"""Bringing over what mp3redactor and videoredactor knew (core/old_apps.py, plan step 10 / D5): the keys by their names in
the credential store, offered for sharing with every Redactor (the family's shared key store, plan D25: once at start-up,
from File > Import every time, never silent), and the notes settings and lookup cache from the folder the person points
at, filling only what is not set here."""

import configparser
import sqlite3

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core import api_keys, notes_settings, old_apps, settings
from core.music import settings as music_settings
from redactor_common.core import secret_store
from redactor_common.core.notes_cache import ResponseCache


def old_ini(path, section, values):
    parser = configparser.ConfigParser(interpolation=None)
    parser[section] = values
    with open(path, "w", encoding="utf-8") as handle:
        parser.write(handle)


def old_cache(path, entries):
    cache = ResponseCache(path)
    for key, body in entries.items():
        cache.put(key, body)
    cache.close()


def test_the_old_apps_keys_are_found_by_name_and_shared_with_every_redactor(fake_keyring):
    secret_store.set_secret("mp3redactor", "discogs_token", "DISCOGS-OLD")
    secret_store.set_secret("videoredactor", "tmdb_api_key", "TMDB-OLD")
    assert api_keys.get_key("discogs") is None  # another app's own entry is never read silently
    found = old_apps.found_keys()
    assert [(k.app, k.name) for k in found] == [("mp3redactor", "discogs_token"), ("videoredactor", "tmdb_api_key")]
    assert old_apps.copy_keys(found) == []
    assert api_keys.get_key("discogs") == "DISCOGS-OLD" and api_keys.get_key("tmdb") == "TMDB-OLD"
    assert fake_keyring.data[("redactor/shared", "discogs_token")] == "DISCOGS-OLD"  # one shared entry for the family
    assert fake_keyring.data[("redactor/mp3redactor", "discogs_token")] == "DISCOGS-OLD"  # the old one stays
    assert old_apps.found_keys() == []  # shared now: nothing more to offer


def test_the_key_this_app_uses_wins_over_another_apps_copy(fake_keyring):
    secret_store.set_secret("mp3redactor", "discogs_token", "DISCOGS-OLD")
    secret_store.set_secret("folderredactor", "discogs_token", "MINE")
    assert api_keys.get_key("discogs") == "MINE"
    [found] = old_apps.found_keys()
    assert (found.app, found.value) == ("folderredactor", "MINE")  # sharing must not change the key used here
    old_apps.copy_keys([found])
    assert api_keys.get_key("discogs") == "MINE" and secret_store.get_key("discogs_token", "mp3redactor") == "MINE"


def test_the_api_keys_dialog_saves_for_the_whole_family(qapp, fake_keyring):
    from gui.api_keys_dialog import ApiKeysDialog

    dlg = ApiKeysDialog()
    field = dlg.fields["tmdb"]
    assert field.shared and "Not set" in field.source_label.text()
    field.edit.setText("TMDB-NEW")
    dlg._save(None)
    assert api_keys.get_key("tmdb") == "TMDB-NEW" and secret_store.get_key("tmdb_api_key", "videoredactor") == "TMDB-NEW"
    assert "shared with videoredactor" in field.source_label.text()
    dlg.deleteLater()


def test_the_mp3redactor_settings_fill_only_what_is_not_set_here(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    old_ini(old / "mp3redactor_settings.ini", "general", {
        "notes_kinds": "artist,album", "notes_discogs_always": "True", "notes_skip_singles": "False",
        "notes_norwegian_numbers": "True", "notes_cache_enabled": "False", "notes_debug_log": "True",
        "notes_last_folder": "D:\\Music", "unrelated": "x"})
    notes_settings.set_last_folder("E:\\Mine")  # chosen here: never overwritten
    lines = old_apps.import_folder(old)
    assert lines == ["mp3redactor: 5 notes setting(s) taken over"]  # not the last folder (set here), not the log switch
    assert music_settings.kinds() == ("artist", "album") and music_settings.discogs_always()
    assert not music_settings.skip_singles() and music_settings.norwegian_numbers() and not notes_settings.cache_enabled()
    assert notes_settings.last_folder() == "E:\\Mine" and not notes_settings.debug_log_enabled()  # the log stays opt-in


def test_the_videoredactor_settings_and_both_caches_are_merged(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    old_ini(old / "videoredactor_settings.ini", "notes", {"kinds": "series", "wikipedia": "0", "cache": "1"})
    old_cache(old / "videoredactor_notes_cache.sqlite", {"tmdb|a": b'"one"', "wiki|b": b'"two"'})
    old_cache(old / "mp3redactor_notes_cache.sqlite", {"mb|c": b'"three"', "wiki|b": b'"older two"'})
    ResponseCache(notes_settings.cache_path()).put("wiki|b", b'"mine"')
    lines = old_apps.import_folder(old)
    assert "videoredactor: 3 notes setting(s) taken over" in lines
    assert "videoredactor: 1 saved lookup answer(s) added to the cache" in lines  # wiki|b was here already
    assert "mp3redactor: 1 saved lookup answer(s) added to the cache" in lines
    assert settings.get_setting("notes.video", "kinds", "") == "series" and not notes_settings.wikipedia_enabled()
    with sqlite3.connect(str(notes_settings.cache_path())) as db:
        rows = dict(db.execute("SELECT key, body FROM cache").fetchall())
    assert set(rows) == {"tmdb|a", "wiki|b", "mb|c"} and rows["wiki|b"] == b'"mine"'


def test_a_folder_without_an_old_app_says_so(tmp_path):
    assert old_apps.import_folder(tmp_path) == [f"No mp3redactor or videoredactor settings or lookup cache in {tmp_path}."]


def test_the_keys_are_offered_once_at_start_up_and_never_copied_without_a_yes(window, monkeypatch, fake_keyring):
    secret_store.set_secret("mp3redactor", "discogs_token", "DISCOGS-OLD")
    asked = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: asked.append(a[2]) or QMessageBox.StandardButton.No))
    window.offer_old_keys()
    assert len(asked) == 1 and "Discogs Token (now in mp3redactor only)" in asked[0] and api_keys.get_key("discogs") is None
    assert "Share these keys with all the Redactors?" in asked[0]
    window.offer_old_keys()
    assert len(asked) == 1  # at start-up only once
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    window.actions_by_key["import_old_apps"].trigger()  # File > Import: the keys are offered again, and a yes copies
    assert api_keys.get_key("discogs") == "DISCOGS-OLD"


def test_opening_a_library_says_what_kind_it_is(window, tmp_path):
    from tests.music_helpers import ultravox_library

    ultravox_library(tmp_path)
    window.open_library_folder(str(tmp_path))
    assert window.library_media == "music" and "(a music library)" in window.folder_label.text()
