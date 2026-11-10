"""The window on a MUSIC library (window review 2026-11-10): the tree with its note lights, Look Up on the selected folder in
the background, the note pane always showing the folder's draft or note, the Match strip, ticks and writing, editing a
note, Undo. Real tagged music files, the real engine and the real write function, the recorded MusicBrainz / Wikipedia
replies as the network (nothing reaches the internet)."""

from pathlib import Path

import pytest

from core import history, notes_debug, notes_settings
from core.music.flow import Fetchers
from gui.lights import LIGHT_EDITED, LIGHT_NONE, LIGHT_NOTE, LIGHT_PLAIN, LIGHT_WAITING, light_icon
from gui.note_pane import VIEW_RAW
from redactor_common.core.notes import STATE_EDITED, STATE_FOREIGN
from tests.music_helpers import (
    FakeFetch, embed_cover, make_audio, make_mp3, musicbrainz_routes, ultravox_fetchers, ultravox_library, wikipedia_routes,
)
from tests.notes_gui_helpers import (  # noqa: F401 -- boxes: a fixture
    boxes, click, item, light, look_up, open_library, pump, select, tick_box, wait_rebuilt,
)
from tests.test_music_levels import genre_wiki

NOTHING_MB = [(r"ws/2/artist\?query", {"artists": []}), (r"ws/2/release-group", {"release-groups": []})]
NO_WIKI = [(r"wikidata", {"entities": {}}), (r"search/title", {"pages": []}), (r"page/summary/", None)]
STAMPED_EDITED = "---\ntitle: X\ngenerator: folderredactor\nnote-format: 3\nbody-sha: 0000\n---\n# X\n\nMy own words.\n"


@pytest.fixture
def lib(tmp_path):
    """The library of a test: beside the app's own files (tests/conftest.py app_files), never holding them."""
    folder = tmp_path / "Library"
    folder.mkdir()
    return folder


def nothing_found() -> Fetchers:
    return Fetchers(mb=FakeFetch(NOTHING_MB), wiki=FakeFetch(NO_WIKI))


def unknown_band(root: Path, name: str, title: str, cover: bytes = b"") -> Path:
    for n, track in enumerate(["Первый", "Второй"], start=1):
        path = make_audio(root / name / f"{title} (2001)" / f"0{n} {track}.flac", track, name, title, n, "2001")
        if cover and n == 1:
            embed_cover(path, cover)
    return root / name


# -- the tree and its lights -------------------------------------------------------------------------------------------

def test_the_tree_shows_every_folder_with_its_note_light(window, lib):
    ultravox_library(lib)
    (lib / "Theirs").mkdir()
    (lib / "Theirs" / "artist.md").write_text("Somebody else's note.\n", encoding="utf-8")
    (lib / "Mine").mkdir()
    (lib / "Mine" / "artist.md").write_text(STAMPED_EDITED, encoding="utf-8")
    (lib / "A").mkdir()  # an alphabet grouping folder: no light
    open_library(window, lib)
    names = [Path(p).name for p in window.tree.visible_paths()[1:]]
    assert names == ["A", "Mine", "Theirs", "Ultravox"]  # every folder, by name, before anything is looked up
    for name in names:
        pump(lambda n=name: window.tree.state_known(str(lib / n)), name)
    assert window.tree.note_state(str(lib / "Theirs"))[0] == STATE_FOREIGN
    assert window.tree.note_state(str(lib / "Mine"))[0] == STATE_EDITED
    assert light(window, lib / "Ultravox") == LIGHT_NONE and light(window, lib / "Theirs") == LIGHT_NOTE
    assert light(window, lib / "Mine") == LIGHT_EDITED
    icon = lambda n: window.tree.item_for(lib / n).icon(0).cacheKey()  # noqa: E731
    assert icon("Theirs") == light_icon(LIGHT_NOTE).cacheKey() and icon("Mine") == light_icon(LIGHT_EDITED).cacheKey()
    assert icon("Ultravox") == light_icon(LIGHT_NONE).cacheKey() and icon("A") == light_icon(LIGHT_PLAIN).cacheKey()


def test_the_pane_shows_the_note_on_disk_or_no_note(window, lib):
    ultravox_library(lib)
    (lib / "Theirs").mkdir()
    (lib / "Theirs" / "artist.md").write_text("# Theirs\n\nSomebody else's note.\n", encoding="utf-8")
    open_library(window, lib)
    select(window, lib / "Theirs")
    pane = window.pane
    assert "Somebody else's note." in pane.preview.toPlainText() and pane.badge.text() == "Note"
    assert "not made by this program" in pane.state_label.text() and pane.edit_button.isVisibleTo(pane)
    select(window, lib / "Ultravox")
    assert "No note in this folder" in pane.preview.toPlainText() and pane.badge.text() == "No note"
    assert not pane.edit_button.isVisibleTo(pane) and not pane.match_row.isVisibleTo(pane)


# -- Look Up and writing -------------------------------------------------------------------------------------------------

def test_look_up_below_fills_the_tree_with_drafts_and_one_button_writes_the_ticked(window, lib, boxes):
    ultravox_library(lib, with_quartet=False)
    look_up(window, lib, ultravox_fetchers(), kinds=("artist", "album"))
    artist, album = lib / "Ultravox", lib / "Ultravox" / "Vienna (1980)"
    assert item(window, artist).proposal.writable and item(window, album).proposal.writable
    assert light(window, artist) == LIGHT_WAITING and light(window, album) == LIGHT_WAITING
    assert tick_box(window, artist) is True and tick_box(window, album) is True  # confident: ticked
    assert window.write_button.text() == "Write 2 ticked notes" and "Looked up 2 folders" in window.progress_label.text()
    select(window, artist)
    pane = window.pane
    assert "Ultravox were a British new wave band" in pane.preview.toPlainText() and pane.badge.text() == "Confident"
    assert not pane.strip_holder.isVisibleTo(pane)  # a settled draft: the Match strip is folded away
    window.tree.item_for(album).setCheckState(0, window.tree.item_for(album).checkState(0).__class__.Unchecked)
    assert window.write_button.text() == "Write 1 ticked note"
    click(window.write_button)
    pump(lambda: window.tree.note_state(str(artist))[1] != "", "the written note's state")
    assert (artist / "artist.md").is_file() and not (album / "album.md").exists()
    assert light(window, artist) == LIGHT_NOTE and light(window, album) == LIGHT_WAITING
    assert "Wrote 1 note." in window.status_bar.currentMessage() and not boxes  # no summary box
    assert notes_settings.last_media() == "music"


def test_look_up_on_one_folder_drafts_what_that_folder_is_whatever_is_ticked(window, lib, boxes):
    ultravox_library(lib, with_quartet=False)
    album = lib / "Ultravox" / "Vienna (1980)"
    look_up(window, album, ultravox_fetchers(), library=lib, below=False, kinds=("artist",))
    assert item(window, album).proposal.kind == "album" and item(window, lib / "Ultravox") is None


def test_enter_in_the_tree_writes_the_selected_draft_and_moves_to_the_next_waiting(window, lib, boxes):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    ultravox_library(lib, with_quartet=False)
    look_up(window, lib, ultravox_fetchers(), kinds=("artist", "album"))
    artist, album = lib / "Ultravox", lib / "Ultravox" / "Vienna (1980)"
    select(window, artist)
    QTest.keyClick(window.tree, Qt.Key.Key_Return)
    assert (artist / "artist.md").is_file() and Path(window._shown) == album
    window.actions_by_key["next_waiting"].trigger()
    assert Path(window._shown) == album  # the only one left


# -- an uncertain folder: the Match strip, Local files, a link, a level --------------------------------------------------

def test_an_uncertain_folder_has_no_tick_box_opens_the_match_strip_and_shows_its_local_files(window, lib, boxes):
    ultravox_library(lib)
    band = unknown_band(lib, "Ленинград", "Пираты XXI века", cover=b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    album = band / "Пираты XXI века (2001)"
    window.actions_by_key["folder_panel"].setChecked(True)
    window._on_toggle_folder_panel()
    look_up(window, lib, Fetchers(mb=FakeFetch(musicbrainz_routes()), wiki=FakeFetch(wikipedia_routes())),
            kinds=("artist", "album"))
    assert not item(window, album).tickable and tick_box(window, album) is None and light(window, album) == LIGHT_WAITING
    select(window, album)
    pane, strip = window.pane, window.pane.strip
    assert pane.strip_holder.isVisibleTo(pane) and pane.match_toggle.isChecked()
    assert strip.local_box.isVisibleTo(strip) and strip.link_box.isVisibleTo(strip)
    assert not strip.tabs.isVisibleTo(strip)  # the note is the pane's, the Local files are under the tree
    view = window.folder_panel.view
    pump(lambda: view.evidence is not None, "the Local files read in the background")
    assert [t.title for t in view.evidence.albums[0].tracks] == ["Первый", "Второй"]


def test_a_bad_link_is_said_under_the_box_and_nothing_is_fetched(window, lib, boxes):
    unknown_band(lib, "Ленинград", "Пираты XXI века")
    unknown_band(lib, "Other Band", "Debut")
    fetchers = nothing_found()
    look_up(window, lib, fetchers, kinds=("artist",))
    select(window, lib / "Ленинград")
    strip = window.pane.strip
    assert strip.link_box.isVisibleTo(strip)
    asked = len(fetchers.mb.urls) + len(fetchers.wiki.urls)
    strip.link_edit.setText("https://evil.example/artist/1")
    click(strip.link_button)
    assert strip.link_error.isVisibleTo(strip) and "musicbrainz.org" in strip.link_error.text()
    assert len(fetchers.mb.urls) + len(fetchers.wiki.urls) == asked  # nothing fetched to refuse it
    strip.link_edit.setText("x")
    assert not strip.link_error.isVisibleTo(strip)  # typing clears the message


def test_a_level_picked_in_the_strip_is_built_on_the_lookup_thread(window, lib, boxes):
    """A folder named after something else (Compilation Box, all Queen inside): unclear; 'Artist folder' builds it again."""
    base = lib / "Compilation Box"
    make_mp3(base / "One (1980)" / "01 a.mp3", "a", "Queen", "One", 1, "1980")
    make_mp3(base / "Two (1981)" / "01 a.mp3", "a", "Queen", "Two", 1, "1981")
    ultravox_library(lib)
    look_up(window, lib, Fetchers(mb=FakeFetch(NOTHING_MB + musicbrainz_routes()), wiki=FakeFetch(wikipedia_routes())),
            kinds=("artist",))
    select(window, base)
    strip = window.pane.strip
    assert strip.level_box.isVisibleTo(strip)
    keys = [strip.level_combo.itemData(i) for i in range(strip.level_combo.count())]
    strip.level_combo.setCurrentIndex(keys.index("artist"))
    strip.level_combo.activated.emit(keys.index("artist"))
    wait_rebuilt(window)
    assert item(window, base).proposal.kind == "artist" and Path(window._shown) == base
    assert "level chosen by you" in " ".join(item(window, base).proposal.level_reasons)


def test_tick_best_guesses_says_so_when_there_is_nothing_to_guess(window, lib, boxes):
    unknown_band(lib, "Band A", "One")
    unknown_band(lib, "Band B", "Two")
    look_up(window, lib, nothing_found(), kinds=("artist",))
    window.actions_by_key["tick_guesses"].trigger()
    assert "No uncertain match has a candidate" in window.status_bar.currentMessage()


def test_a_genre_folder_has_the_genres_box_and_looks_the_folder_up_again(window, lib, boxes):
    music = lib / "Music"
    ultravox_library(music / "New Wave")
    ultravox_library(music / "Synth")
    look_up(window, music, Fetchers(mb=FakeFetch(NOTHING_MB), wiki=genre_wiki()), kinds=("genre",))
    assert item(window, music / "New Wave") is not None and item(window, music / "Synth") is not None
    select(window, music / "Synth")
    window.pane.match_toggle.setChecked(True)
    strip = window.pane.strip
    assert strip.genres_box.isVisibleTo(strip) and strip.genres_edit.text() == "Synth"
    strip.genres_edit.setText("New wave music")
    click(strip.genres_button)
    wait_rebuilt(window)
    assert "New wave is a music genre" in item(window, music / "Synth").proposal.note_text


# -- nothing to look up ----------------------------------------------------------------------------------------------------

def test_an_album_folder_with_artist_notes_only_says_so_not_library_root(window, lib, boxes):
    ultravox_library(lib)
    album = lib / "Ultravox" / "Vienna (1980)"
    look_up(window, album, ultravox_fetchers(), library=lib, kinds=("artist",))
    assert "This is an album folder" in window.progress_label.text() and not boxes


def test_a_library_root_says_so(window, lib, boxes):
    root = lib / "Music"
    (root / "Empty").mkdir(parents=True)
    notes_settings.set_last_media("music")  # nothing in it tells music from video: the kind used last time
    look_up(window, root, ultravox_fetchers(), kinds=("artist", "genre"))
    assert "looks like a library root" in window.progress_label.text()


def test_the_media_type_comes_from_the_folder_else_the_library_else_the_last_one_else_it_is_asked(window, lib, monkeypatch):
    music, empty = lib / "Music", lib / "Empty"
    ultravox_library(music)
    empty.mkdir()
    asked = []
    monkeypatch.setattr(window, "_ask_media", lambda: asked.append(1) or "video")
    window.open_library_folder(str(music))
    assert window.media_for(str(music / "Ultravox")) == "music"
    window.open_library_folder(str(empty))
    assert window.media_for(str(empty)) == "video" and asked == [1]  # never used before: asked, kept for this library
    assert window.media_for(str(empty)) == "video" and asked == [1]
    notes_settings.set_last_media("music")
    window.open_library_folder(str(empty))
    assert window.media_for(str(empty)) == "music" and asked == [1]  # used before: the last one, no question


# -- editing a note, Undo ----------------------------------------------------------------------------------------------------

def test_a_note_edited_in_the_pane_is_saved_and_reads_as_edited_by_you(window, lib, boxes, recycle_bin):
    folder = lib / "Theirs"
    folder.mkdir()
    (folder / "artist.md").write_text("# Theirs\n\nOld words.\n", encoding="utf-8")
    open_library(window, lib)
    select(window, folder)
    window.actions_by_key["edit_note"].trigger()
    pane = window.pane
    assert pane.is_editing() and pane.current_view() == VIEW_RAW and not pane.raw.isReadOnly()
    pane.raw.setPlainText("# Theirs\n\nNew words.\n")
    click(pane.save_button)
    assert (folder / "artist.md").read_text(encoding="utf-8") == "# Theirs\n\nNew words.\n"
    assert len(recycle_bin.trashed) == 1 and not pane.is_editing() and "New words." in pane.preview.toPlainText()


def test_moving_away_from_an_unsaved_edit_asks_first(window, lib, boxes, recycle_bin):
    folder = lib / "Theirs"
    folder.mkdir()
    (folder / "artist.md").write_text("# Theirs\n\nOld words.\n", encoding="utf-8")
    (lib / "Other").mkdir()
    open_library(window, lib)
    select(window, folder)
    window.pane.start_edit()
    window.pane.raw.setPlainText("# Theirs\n\nChanged.\n")
    window.tree.select(lib / "Other")  # answered No (= Discard is not Save): the change is dropped
    assert boxes.said("Save the changes to the note first?") and Path(window._shown) == lib / "Other"
    assert "Old words." in (folder / "artist.md").read_text(encoding="utf-8")


def test_undo_takes_back_the_last_note_written_with_history_on(window, lib, boxes, recycle_bin):
    history.set_history_enabled(True)
    ultravox_library(lib, with_quartet=False)
    look_up(window, lib, ultravox_fetchers(), kinds=("artist",))
    artist = lib / "Ultravox"
    window.actions_by_key["write_ticked"].trigger()
    assert (artist / "artist.md").is_file()
    window.actions_by_key["undo"].trigger()
    assert not (artist / "artist.md").exists() and len(recycle_bin.trashed) == 1


def test_undo_without_history_says_why(window, lib, boxes):
    ultravox_library(lib, with_quartet=False)
    look_up(window, lib, ultravox_fetchers(), kinds=("artist",))
    window.actions_by_key["write_ticked"].trigger()
    window.actions_by_key["undo"].trigger()
    assert boxes.said("Undo needs Tools > History") and (lib / "Ultravox" / "artist.md").is_file()


# -- the troubleshooting log ---------------------------------------------------------------------------------------

def test_the_review_list_log_is_opt_in_from_preferences_and_can_be_deleted(window, monkeypatch, qapp):
    from PyQt6.QtWidgets import QMessageBox

    from gui.preferences_dialog import PreferencesDialog

    said = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: said.append(a[2]) or QMessageBox.StandardButton.Ok))
    monkeypatch.delenv("FOLDERREDACTOR_NOTES_DEBUG", raising=False)
    notes_debug.set_enabled(None)
    dlg = PreferencesDialog(window)
    assert not dlg.notes_debug_check.isChecked() and not dlg.delete_debug_button.isEnabled()
    dlg.notes_debug_check.setChecked(True)
    dlg._on_ok()
    assert notes_settings.debug_log_enabled() and notes_debug.enabled()
    notes_debug.record("current", rows=2, touched=["Ultravox"])
    assert notes_debug.log_exists()
    dlg2 = PreferencesDialog(window)
    assert dlg2.delete_debug_button.isEnabled()
    click(dlg2.delete_debug_button)
    assert not notes_debug.log_exists() and said
    notes_debug.set_enabled(None)
