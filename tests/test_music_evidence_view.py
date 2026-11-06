"""The Local files tab's view (gui/music_evidence_view.py, moved from mp3redactor): a small thumbnail of the cover, the files
read in the background once (then from the cache), 'no cover' and the album captions of an artist, and a slow answer for a
row the person has left is never shown."""

import time

import pytest
from PyQt6.QtWidgets import QApplication

from gui import music_evidence_view as view_module
from gui.music_evidence_view import LocalEvidenceView, make_thumb
from tests.test_music_evidence import ALBUM, BAND, cyrillic_album, png_bytes


@pytest.fixture(autouse=True)
def _fresh(qapp):
    view_module.clear_cache()
    yield
    LocalEvidenceView.loader = None
    view_module.clear_cache()


def wait_for(view, kind="album", timeout=10):
    end = time.perf_counter() + timeout
    while view.evidence is None or view.evidence.kind != kind:
        QApplication.processEvents()
        assert time.perf_counter() < end, "the files were not read"
        time.sleep(0.01)


def test_the_thumbnail_is_small_keeps_the_aspect_ratio_and_a_bad_picture_is_none():
    from PyQt6.QtGui import QImage

    thumb = make_thumb(png_bytes(640, 320))
    image = QImage.fromData(thumb)
    assert (image.width(), image.height()) == (160, 80) and len(thumb) < 30_000
    assert make_thumb(b"not a picture") is None


@pytest.mark.parametrize("ext", [".mp3", ".flac", ".m4a"])
def test_the_view_shows_the_cover_and_the_text_and_reads_in_the_background_once(tmp_path, ext):
    folder = cyrillic_album(tmp_path, "embedded", ext=ext)
    calls = []

    def counting(paths):
        from core.music.local import default_loader

        calls.append(len(paths))
        return default_loader(paths)

    LocalEvidenceView.loader = counting
    view = LocalEvidenceView()
    view.show_folder(folder, "album")
    assert view.evidence is None and view.status.text()  # not blocked: the answer comes later
    wait_for(view)
    assert view.thumb_labels[0].property("has_cover") is True and view.thumb_labels[0].pixmap().width() <= 160
    text = view.text.toPlainText()
    assert "Мне хочется кричать" in text and BAND in text and "3 music file(s)" in text
    view.show_folder(folder, "album")  # a second time: from the cache
    assert view.evidence is not None and calls == [3]


def test_no_cover_says_so_and_an_artist_has_captions(tmp_path):
    cyrillic_album(tmp_path, "none")
    view = LocalEvidenceView()
    view.show_folder(tmp_path / BAND / f"{ALBUM} (2000)", "album")
    wait_for(view)
    assert view.thumb_labels[0].text() == "no cover" and view.thumb_labels[0].property("has_cover") is False
    view.show_folder(tmp_path / BAND, "artist")
    wait_for(view, "artist")
    assert [c.text() for c in view.caption_labels] == [ALBUM]


def test_a_slow_answer_for_a_row_left_behind_is_not_shown(tmp_path):
    cyrillic_album(tmp_path, "none")
    view = LocalEvidenceView()
    view.show_folder(tmp_path / BAND / f"{ALBUM} (2000)", "album")
    view.clear()  # another row (or none) was selected
    time.sleep(0.5)
    QApplication.processEvents()
    assert view.evidence is None and view.text.toPlainText() == ""
