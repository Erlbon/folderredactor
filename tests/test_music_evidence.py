"""'What is in this folder': the Local files tab of the review page. A pure display model (LocalAlbum -> what is shown) and
the real reading of a scratch album tagged in Cyrillic (embedded cover in every format, folder.jpg, no cover, 70 tracks).
The view and the review dialog tests of mp3redactor's file come with the review page, plan step 9."""

from pathlib import Path

import pytest
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QColor, QImage

from core.music.evidence import MAX_TRACKS, Evidence, album_evidence, evidence_lines, read_evidence, seconds_text
from core.music.local import LocalAlbum, LocalTrack
from tests.music_helpers import FORMATS, embed_cover, make_audio, make_mp3

BAND, ALBUM = "Ленинград", "Дачники"
TRACKS = ["Мне хочется кричать", "Вояж", "Дачники"]


@pytest.fixture(autouse=True)
def _qt(qapp):
    """QImage needs a QApplication (the pictures are made with Qt)."""


def png_bytes(width=300, height=200, color="#c04040"):
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    raw = QByteArray()
    buffer = QBuffer(raw)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(raw)


def cyrillic_album(root, with_cover="embedded", count=3, folder=f"{ALBUM} (2000)", ext=".mp3"):
    for i in range(count):
        title = TRACKS[i] if i < len(TRACKS) else f"Трек {i + 1}"
        path = make_audio(root / BAND / folder / f"{i + 1:02d} t{ext}", title, BAND, ALBUM, i + 1, "2000")
        if with_cover == "embedded" and i == 0:
            embed_cover(path, png_bytes(), "image/png")
    if with_cover == "folder":
        image = QImage(120, 120, QImage.Format.Format_RGB32)
        image.fill(QColor("#4040c0"))
        assert image.save(str(root / BAND / folder / "folder.jpg"), "JPG")
    return root / BAND / folder


# -- the display model, pure -------------------------------------------------------------------------------------------

def test_seconds_text():
    assert seconds_text(None) == "" and seconds_text(0) == "" and seconds_text(65.4) == "1:05" and seconds_text(3600) == "60:00"


def local_album(count, folder="Дачники (2000)"):
    tracks = [LocalTrack(path=Path(f"{i}.mp3"), title=f"Трек {i}", track=i, seconds=61 + i, artist=BAND, album=ALBUM, year="2000")
              for i in range(1, count + 1)]
    return LocalAlbum(folder=Path(folder), title=ALBUM, year="2000", tag_titles=[ALBUM], artist=BAND, tracks=tracks)


def test_the_album_display_model_keeps_the_original_script_and_the_tags():
    model = album_evidence(local_album(3), (b"x", "embedded"))
    assert [t.title for t in model.tracks] == ["Трек 1", "Трек 2", "Трек 3"]
    assert (model.album_tag, model.artist_tag, model.year_tag, model.files) == (ALBUM, BAND, "2000", 3)
    assert model.tracks[0].number == "1" and model.tracks[0].length == "1:02" and model.cover_from == "embedded"
    lines = evidence_lines(Evidence(kind="album", folder_name="x", albums=[model]))
    assert lines[0] == "Folder: Дачники (2000)" and "album 'Дачники'" in lines[1] and f"artist '{BAND}'" in lines[1]
    assert lines[2] == "3 music file(s)" and lines[3] == f"1. Трек 1 - {BAND} (1:02)"


def test_seventy_tracks_list_sixty_and_say_how_many_more():
    model = album_evidence(local_album(70))
    assert len(model.tracks) == MAX_TRACKS == 60 and model.more_tracks == 10 and model.files == 70
    lines = evidence_lines(Evidence(kind="album", albums=[model]))
    assert lines[-1] == "... and 10 more" and len(lines) == 3 + 60 + 1


def test_a_track_without_a_title_shows_its_file_name():
    local = local_album(1)
    local.tracks[0].title = ""
    local.tracks[0].path = Path("01 Вояж.mp3")
    assert album_evidence(local).tracks[0].title == "01 Вояж"


# -- reading real folders ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("ext", FORMATS)
def test_an_embedded_cover_and_the_cyrillic_tracks_are_read_in_every_format(tmp_path, ext):
    folder = cyrillic_album(tmp_path, "embedded", ext=ext)
    evidence = read_evidence(folder, "album")
    [album] = evidence.albums
    assert album.cover_from == "embedded" and album.cover == png_bytes() and album.files == 3
    assert [t.title for t in album.tracks] == TRACKS and album.artist_tag == BAND and album.album_tag == ALBUM


def test_the_folder_image_is_used_when_nothing_is_embedded(tmp_path):
    folder = cyrillic_album(tmp_path, "folder")
    [album] = read_evidence(folder, "album").albums
    assert album.cover_from == "folder.jpg" and album.cover


def test_no_cover_is_none(tmp_path):
    folder = cyrillic_album(tmp_path, "none", ext=".flac")
    [album] = read_evidence(folder, "album").albums
    assert album.cover is None and album.tracks


def test_an_artist_lists_its_albums_and_up_to_six_covers(tmp_path):
    for n in range(8):
        path = make_mp3(tmp_path / BAND / f"Альбом {n} (200{n})" / "01 a.mp3", "Т", BAND, f"Альбом {n}", 1, f"200{n}")
        make_mp3(tmp_path / BAND / f"Альбом {n} (200{n})" / "02 b.mp3", "Т2", BAND, f"Альбом {n}", 2, f"200{n}")
        if n % 2 == 0:
            embed_cover(path, png_bytes(), "image/png")
    make_audio(tmp_path / BAND / "Single.flac", "Сингл", BAND)  # a loose file beside the albums
    evidence = read_evidence(tmp_path / BAND, "artist")
    assert len(evidence.albums) == 8 and evidence.covers == 6 and evidence.loose_files == 1
    assert [a.files for a in evidence.albums] == [2] * 8
    assert evidence.albums[0].cover and evidence.albums[1].cover is None and evidence.albums[7].album_tag == ""  # beyond 6: no read
    lines = evidence_lines(evidence)
    assert lines[1] == "8 album folder(s), 17 music file(s), 1 directly in the folder"
    assert lines[2] == f"Альбом 0 (2000): 2 track(s) (tagged 'Альбом 0' by '{BAND}')"


def test_an_unreadable_folder_is_said_not_raised(tmp_path):
    evidence = read_evidence(tmp_path / "gone", "album")
    assert evidence.albums and evidence.albums[0].files == 0 or evidence.error
