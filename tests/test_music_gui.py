"""Notes > Create Notes... on a MUSIC library through the REAL main window (plan step 9): real tagged music files, the real
engine and the real write function, the recorded MusicBrainz / Wikipedia replies as the network (nothing reaches the
internet), the shared folder question and the shared review page (its template is mp3redactor's page) driven by their
widgets. Each test is one of mp3redactor's window-flow scenarios, rewritten for this window: it opens a library folder
instead of loading files into a table."""

from pathlib import Path

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core import notes_debug, notes_settings
from core.music import settings as music_settings
from core.music.flow import Fetchers
from gui.music_notes import KIND_CHECKS
from tests.music_helpers import (
    FakeFetch, embed_cover, make_audio, make_mp3, musicbrainz_routes, ultravox_fetchers, ultravox_library, wikipedia_routes,
)
from tests.notes_gui_helpers import Script, boxes, click, review, run, scope, wait  # noqa: F401 -- boxes: a fixture
from tests.test_music_levels import genre_wiki

NOTHING_MB = [(r"ws/2/artist\?query", {"artists": []}), (r"ws/2/release-group", {"release-groups": []})]
NO_WIKI = [(r"wikidata", {"entities": {}}), (r"search/title", {"pages": []}), (r"page/summary/", None)]


def nothing_found() -> Fetchers:
    return Fetchers(mb=FakeFetch(NOTHING_MB), wiki=FakeFetch(NO_WIKI))


def choose(folder: Path, *kinds: str):
    """The folder question: this folder's radio (else Another folder...), and exactly these kinds ticked."""
    def setup(dialog):
        radio = next((r for r, p in dialog.radios if Path(p) == folder), None)
        (radio or dialog.other_radio).click()
        if kinds:
            for key, box in dialog.kind_boxes.items():
                box.setChecked(key in kinds)
    return setup


def row_of(page, name: str):
    tree = page.tree
    index = next(i for i, it in enumerate(page.session.items) if it.proposal.folder.name == name)
    row = next(tree.topLevelItem(r) for r in range(tree.topLevelItemCount())
               if tree.topLevelItem(r).data(0, Qt.ItemDataRole.UserRole) == index)
    tree.setCurrentItem(row)
    return index, row


# -- the media type and the question ---------------------------------------------------------------------------------

def test_a_music_library_gets_the_music_question_with_mp3redactors_kinds_artist_only_by_default(window, monkeypatch, tmp_path, boxes):
    ultravox_library(tmp_path)
    seen = {}

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        seen["kinds"] = sorted({i.proposal.kind for i in page.session.items})
        seen["banner"] = page.banner_label.text()
        page.done(0)

    def look(dialog):
        seen["labels"] = [b.text() for b in dialog.kind_boxes.values()]
        seen["ticked"] = [k for k, b in dialog.kind_boxes.items() if b.isChecked()]
        choose(tmp_path)(dialog)

    run(window, monkeypatch, tmp_path, ultravox_fetchers(), scenario, choose=look)
    assert seen["labels"] == [label for _key, label in KIND_CHECKS] and seen["ticked"] == ["artist"]
    assert seen["kinds"] == ["artist"] and "Looked up: artist notes only (no album lookups)." in seen["banner"]
    assert "Discogs token not set" in seen["banner"] and notes_settings.last_media() == "music"


def test_the_media_type_comes_from_the_files_else_the_last_one_else_it_is_asked(window, tmp_path, monkeypatch):
    music, video, empty = tmp_path / "Music", tmp_path / "Video", tmp_path / "Empty"
    ultravox_library(music)
    (video / "Heat (1995)").mkdir(parents=True)
    (video / "Heat (1995)" / "Heat.1995.mkv").write_bytes(b"")
    empty.mkdir()
    asked = []
    monkeypatch.setattr(window, "_ask_media", lambda: asked.append(1) or "video")
    window.open_library_folder(str(music))
    assert window.notes_media() == "music"
    window.open_library_folder(str(video))
    assert window.notes_media() == "video"
    window.open_library_folder(str(empty))
    assert window.notes_media() == "video" and asked == [1]  # never used before: asked
    notes_settings.set_last_media("music")
    assert window.notes_media() == "music" and asked == [1]  # used before: the last one, no question


# -- one at a time -----------------------------------------------------------------------------------------------------

def test_a_single_artist_opens_one_at_a_time_and_skip_and_write_do_what_they_say(window, monkeypatch, tmp_path, boxes):
    ultravox_library(tmp_path, with_quartet=False)

    def scenario():
        yield from wait(lambda: review() is not None, "review page")
        dlg = review()
        assert dlg.view == "one" and dlg.header_label.text() == "Create notes  1 of 2"
        assert dlg.one_panel.kind_label.text().startswith("Note: artist.md") and dlg.one_panel.badge.text() == "Confident"
        assert "Ultravox were a British new wave band" in dlg.one_panel.preview.toPlainText()
        assert dlg.one_panel.raw.toPlainText().startswith("---\ntitle: Ultravox")
        click(dlg.skip_button)
        assert dlg.header_label.text() == "Create notes  2 of 2" and not (tmp_path / "Ultravox" / "artist.md").exists()
        expected = dlg.session.items[1].proposal.note_text
        click(dlg.write_button)
        yield from wait(lambda: review() is None, "closed after the last note", 10)
        album = tmp_path / "Ultravox" / "Vienna (1980)" / "album.md"
        assert album.read_text(encoding="utf-8") == expected.replace("\r\n", "\n").rstrip("\n") + "\n"
        assert "status: draft" in expected.split("---")[1] and not (tmp_path / "Ultravox" / "artist.md").exists()

    run(window, monkeypatch, tmp_path, ultravox_fetchers(), scenario, choose=choose(tmp_path, "artist", "album"))
    assert boxes.said("Written: 1") and boxes.said("Skipped: 1")
    assert notes_settings.last_folder() == str(tmp_path) and music_settings.kinds() == ("artist", "album")


def test_after_artist_notes_the_album_notes_of_those_artists_are_one_yes_away(window, monkeypatch, tmp_path, boxes):
    """'Create the album notes for these artists too': asked when the page closes; a yes looks up only their albums."""
    ultravox_library(tmp_path, with_quartet=False)
    boxes.yes.append("Create the album notes")
    pages = []

    def scenario():
        yield from wait(lambda: review() is not None, "the artist page")
        first = review()
        pages.append(sorted(i.proposal.kind for i in first.session.items))
        click(first.write_button)  # the only artist: the page closes and asks
        yield from wait(lambda: review() is not None and review() is not first, "the album page")
        second = review()
        pages.append(sorted(i.proposal.kind for i in second.session.items))
        second.done(0)

    run(window, monkeypatch, tmp_path, ultravox_fetchers(), scenario, choose=choose(tmp_path, "artist"))
    assert pages == [["artist"], ["album"]] and (tmp_path / "Ultravox" / "artist.md").is_file()
    assert boxes.said("1 artist note written.") and not (tmp_path / "Ultravox" / "Vienna (1980)" / "album.md").exists()


# -- the list: uncertain rows, the Local files tab, Look up by link, best guesses ---------------------------------------

def unknown_band(root: Path, name: str, title: str, cover: bytes = b"") -> Path:
    for n, track in enumerate(["Первый", "Второй"], start=1):
        path = make_audio(root / name / f"{title} (2001)" / f"0{n} {track}.flac", track, name, title, n, "2001")
        if cover and n == 1:
            embed_cover(path, cover)
    return root / name


def test_an_uncertain_row_cannot_be_ticked_says_why_and_opens_on_its_local_files(window, monkeypatch, tmp_path, boxes):
    ultravox_library(tmp_path)
    unknown_band(tmp_path, "Ленинград", "Пираты XXI века", cover=b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    seen = {}

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        assert page.view == "list" and page.tick_guesses_button.isVisibleTo(page)
        index, row = row_of(page, "Пираты XXI века (2001)")
        item = page.session.items[index]
        assert not item.tickable and not (row.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        assert page.row_hint.text().endswith("Not tickable yet: pick a candidate or a level first.")
        panel = page.list_panel
        assert panel.tabs.currentIndex() == panel.evidence_tab and panel.tabs.isTabVisible(panel.evidence_tab)
        yield from wait(lambda: panel.evidence_view.evidence is not None, "the files read in the background")
        seen["evidence"] = panel.evidence_view.text.toPlainText() if hasattr(panel.evidence_view, "text") else ""
        seen["evidence_albums"] = [a.title for a in panel.evidence_view.evidence.albums]
        seen["tracks"] = [t.title for t in panel.evidence_view.evidence.albums[0].tracks]
        assert panel.local_box.isVisibleTo(panel) and panel.link_box.isVisibleTo(panel)
        index, _ = row_of(page, "Ultravox")
        assert page.session.items[index].ticked and panel.tabs.currentIndex() == 0  # a confident row: the preview
        page.done(0)

    run(window, monkeypatch, tmp_path, Fetchers(mb=FakeFetch(NOTHING_MB[:0] + musicbrainz_routes()),
                                                wiki=FakeFetch(wikipedia_routes())),
        scenario, choose=choose(tmp_path, "artist", "album"))
    assert seen["tracks"] == ["Первый", "Второй"]


def test_a_bad_link_is_said_under_the_box_and_nothing_is_fetched(window, monkeypatch, tmp_path, boxes):
    unknown_band(tmp_path, "Ленинград", "Пираты XXI века")
    unknown_band(tmp_path, "Other Band", "Debut")
    fetchers = nothing_found()

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        row_of(page, "Ленинград")
        panel = page.list_panel
        assert panel.link_box.isVisibleTo(panel)
        asked = len(fetchers.mb.urls) + len(fetchers.wiki.urls)
        panel.link_edit.setText("https://evil.example/artist/1")
        click(panel.link_button)
        assert panel.link_error.isVisibleTo(panel) and "musicbrainz.org" in panel.link_error.text()
        assert len(fetchers.mb.urls) + len(fetchers.wiki.urls) == asked  # nothing fetched to refuse it
        panel.link_edit.setText("x")
        assert not panel.link_error.isVisibleTo(panel)  # typing clears the message
        page.done(0)

    run(window, monkeypatch, tmp_path, fetchers, scenario, choose=choose(tmp_path, "artist"))


def test_a_level_picked_from_the_list_is_built_at_once_in_place(window, monkeypatch, tmp_path, boxes):
    """A folder named after something else (Compilation Box, all Queen inside): unclear; 'Artist folder' builds it again at
    once, and the row stays where it is."""
    base = tmp_path / "Compilation Box"
    make_mp3(base / "One (1980)" / "01 a.mp3", "a", "Queen", "One", 1, "1980")
    make_mp3(base / "Two (1981)" / "01 a.mp3", "a", "Queen", "Two", 1, "1981")
    ultravox_library(tmp_path)
    fetchers = Fetchers(mb=FakeFetch(NOTHING_MB + musicbrainz_routes()), wiki=FakeFetch(wikipedia_routes()))

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        index, row = row_of(page, "Compilation Box")
        panel = page.list_panel
        assert panel.level_box.isVisibleTo(panel)
        keys = [panel.level_combo.itemData(i) for i in range(panel.level_combo.count())]
        assert "artist" in keys
        rows_before = [page.tree.topLevelItem(r) for r in range(page.tree.topLevelItemCount())]
        panel.level_combo.setCurrentIndex(keys.index("artist"))
        panel.level_combo.activated.emit(keys.index("artist"))
        yield from wait(lambda: page.session.items[index].proposal.kind == "artist", "the rebuilt row")
        assert [page.tree.topLevelItem(r) for r in range(page.tree.topLevelItemCount())] == rows_before
        assert page.tree.currentItem() is row and "level chosen by you" in " ".join(page.session.items[index].proposal.level_reasons)
        page.done(0)

    run(window, monkeypatch, tmp_path, fetchers, scenario, choose=choose(tmp_path, "artist"))


def test_tick_best_guesses_says_so_when_there_is_nothing_to_guess(window, monkeypatch, tmp_path, boxes):
    unknown_band(tmp_path, "Band A", "One")
    unknown_band(tmp_path, "Band B", "Two")

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        click(page.tick_guesses_button)
        assert boxes.said("No uncertain match has a candidate")
        page.done(0)

    run(window, monkeypatch, tmp_path, nothing_found(), scenario, choose=choose(tmp_path, "artist"))


# -- genre folders ---------------------------------------------------------------------------------------------------

def test_a_genre_row_has_the_genres_box_and_looks_the_folder_up_again(window, monkeypatch, tmp_path, boxes):
    ultravox_library(tmp_path / "Music" / "New Wave")
    ultravox_library(tmp_path / "Music" / "Synth")
    wiki = genre_wiki()

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        page = review()
        assert sorted(i.proposal.folder.name for i in page.session.items) == ["New Wave", "Synth"]
        index, _ = row_of(page, "Synth")
        panel = page.list_panel
        assert panel.genres_box.isVisibleTo(panel) and panel.genres_edit.text() == "Synth"
        assert not panel.evidence_view or not panel.tabs.isTabVisible(panel.evidence_tab)  # no Local files for a genre
        panel.genres_edit.setText("New wave music")
        click(panel.genres_button)
        yield from wait(lambda: "New wave is a music genre" in page.session.items[index].proposal.note_text, "rebuilt")
        page.done(0)

    run(window, monkeypatch, tmp_path / "Music", Fetchers(mb=FakeFetch(NOTHING_MB), wiki=wiki), scenario,
        choose=choose(tmp_path / "Music", "genre"))


# -- nothing to do ---------------------------------------------------------------------------------------------------

def test_an_album_folder_with_artist_notes_only_says_so_not_library_root(window, monkeypatch, tmp_path, boxes):
    ultravox_library(tmp_path)
    album = tmp_path / "Ultravox" / "Vienna (1980)"

    def scenario():
        yield from wait(lambda: boxes.said("This is an album folder"), "the message")

    run(window, monkeypatch, album, ultravox_fetchers(), scenario, must_finish=False, choose=choose(album, "artist"))
    assert review() is None


def test_a_library_root_says_so(window, monkeypatch, tmp_path, boxes):
    root = tmp_path / "Music"
    root.mkdir()
    make_mp3(root / "loose.mp3", "x")

    def scenario():
        yield from wait(lambda: boxes.said("looks like a library root"), "the message")

    run(window, monkeypatch, root, ultravox_fetchers(), scenario, must_finish=False, choose=choose(root, "artist", "genre"))


# -- the troubleshooting log ---------------------------------------------------------------------------------------

def test_the_review_list_log_is_opt_in_from_preferences_and_can_be_deleted(window, monkeypatch, qapp):
    from gui.preferences_dialog import PreferencesDialog

    said = []
    from PyQt6.QtWidgets import QMessageBox

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
