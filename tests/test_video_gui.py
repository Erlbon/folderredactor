"""The window on a VIDEO library (window review 2026-11-10): real folders of video files, the real engine and the real write
function, recorded-shape TMDB / Wikipedia replies as the network (nothing reaches the internet). Look Up on the selected
folder, the drafts in the tree, a pick in the Match strip, the one write button. (Moved from videoredactor with the notes,
plan step 5; the `window` fixture is conftest's.)"""

import pytest
from PyQt6.QtCore import Qt

from core import notes_settings
from gui.lights import LIGHT_NOTE, LIGHT_WAITING
from tests.notes_gui_helpers import (  # noqa: F401 -- boxes: a fixture
    boxes, click, item, light, look_up, open_library, pump, select, tick_box, wait_rebuilt,
)
from tests.video_helpers import BREAKING_BAD, fake_fetchers, hit, make_movie, make_series, touch


def test_a_series_is_looked_up_shown_in_the_pane_and_written(window, tmp_path, boxes):
    library = tmp_path / "Library"
    show = make_series(library)
    look_up(window, library, fake_fetchers())
    proposal = item(window, show).proposal
    assert proposal.writable and light(window, show) == LIGHT_WAITING and tick_box(window, show) is True
    select(window, show)
    pane = window.pane
    assert pane.path_label.text() == str(show) and pane.badge.text() == "Confident"
    assert pane.state_label.text().startswith("series.md: draft")
    assert "It ran for five seasons." in pane.preview.toPlainText()
    assert pane.raw.toPlainText().startswith("---\ntitle: Breaking Bad")
    click(window.write_button)
    pump(lambda: window.tree.note_state(str(show))[1] != "", "the written note's state")
    assert (show / "series.md").read_text(encoding="utf-8") == proposal.note_text.replace("\r\n", "\n").rstrip("\n") + "\n"
    assert "status: draft" in proposal.note_text.split("---")[1] and light(window, show) == LIGHT_NOTE
    assert notes_settings.last_folder() == str(library) and notes_settings.last_media() == "video"


def multi_fetchers():
    other = hit("tv", 99, "Dark", "2017-12-01", "A German series")
    dark_two = hit("tv", 100, "Dark", "2019-01-01", "Another Dark")
    details = lambda ident, year: dict(BREAKING_BAD, id=ident, name="Dark", original_name="Dark", first_air_date=f"{year}-01-01",
                                       external_ids={"imdb_id": ""})
    return fake_fetchers(tmdb_extra=[(r"/search/tv\?.*query=Dark", {"results": [other, dark_two]}),
                                     (r"/tv/99\?", details(99, 2017)), (r"/tv/100\?", details(100, 2019))])


def test_several_folders_the_tick_rules_a_pick_in_the_strip_and_a_blocked_write(window, tmp_path, boxes):
    library = tmp_path / "Library"
    show = make_series(library)
    movie = make_movie(library)
    for episode in (1, 2):
        touch(library / "Dark" / f"Dark.S01E0{episode}.mkv")  # two TMDB titles are called Dark
    dark = library / "Dark"
    look_up(window, library, multi_fetchers())
    assert tick_box(window, show) is True and tick_box(window, movie) is True
    assert tick_box(window, dark) is None and not item(window, dark).ticked  # uncertain: no tick box at all
    select(window, dark)
    strip = window.pane.strip
    assert window.pane.strip_holder.isVisibleTo(window.pane) and strip.candidate_table.rowCount() == 2
    strip.candidate_table.selectRow(0)
    strip.candidate_table.activated.emit(strip.candidate_table.currentIndex())  # double-click / Enter builds it
    wait_rebuilt(window)
    assert item(window, dark).proposal.confidence.value == "confident" and tick_box(window, dark) is True
    blocker = show / "Series.MD"  # an existing note that appears after the lookup blocks its write, never touched
    blocker.write_text("mine\n", encoding="utf-8")
    window.actions_by_key["write_ticked"].trigger()
    assert blocker.read_text(encoding="utf-8") == "mine\n" and (movie / "about.md").is_file()
    assert boxes.said("Not written:") and "Wrote 2 notes." in window.status_bar.currentMessage()


def test_without_a_tmdb_key_it_says_so_and_looks_nothing_up(window, monkeypatch, tmp_path, boxes):
    library = tmp_path / "Library"
    make_series(library)
    from core.video.flow import Fetchers

    fetchers = Fetchers(tmdb=lambda r: pytest.fail("no request without a key"), key=None)
    monkeypatch.setattr("gui.video_notes.get_api_key", lambda: None)
    monkeypatch.setattr("core.video.tmdb.get_api_key", lambda: None)
    look_up(window, library, fetchers)
    assert boxes.said("API key") and not window.session.items


def test_nothing_to_look_up_says_why_in_the_window(window, tmp_path, boxes):
    library = tmp_path / "Library"
    show = make_series(library)
    (show / "series.md").write_text("mine\n", encoding="utf-8")
    look_up(window, library, fake_fetchers())
    assert "Nothing to look up in this folder or below: 1 folder(s) already have a note." in window.progress_label.text()
    assert not boxes


def test_the_drafts_of_a_library_are_dropped_when_another_opens_asked_first_when_ticked(window, tmp_path, boxes):
    library, other = tmp_path / "Library", tmp_path / "Other"
    make_series(library)
    other.mkdir()
    look_up(window, library, fake_fetchers())
    assert not window.open_library_folder(str(other))  # 1 ticked, answered No
    assert boxes.said("1 ticked note has not been written") and window.session.items
    boxes.yes.append("ticked note")
    assert window.open_library_folder(str(other)) and not window.session.items


def test_the_tree_offers_check_boxes_only_where_a_draft_can_be_written(window, tmp_path, boxes):
    library = tmp_path / "Library"
    make_series(library)
    open_library(window, library)
    row = window.tree.item_for(library / "Breaking Bad (2008)")
    assert not (row.flags() & Qt.ItemFlag.ItemIsUserCheckable)
