"""The music file reader (core/music/tags.py): the same fields from MP3, FLAC, M4A, Ogg Vorbis and Opus, on tiny real files
built and tagged in tmp_path; a damaged file is said, never raised."""

import pytest

from core.music.tags import AUDIO_EXTENSIONS, is_audio_name, load_files, read_cover, read_tags
from tests.music_helpers import FORMATS, SECONDS, embed_cover, make_audio


@pytest.mark.parametrize("ext", FORMATS)
def test_every_format_gives_the_same_fields(tmp_path, ext):
    path = make_audio(tmp_path / f"03 Song{ext}", "Sång Ä", "Artist", "Album", 3, "1980-07-11", albumartist="Band",
                      composer="Writer", genre="New Wave", disc=2)
    tags = read_tags(path)
    assert tags.load_error == ""
    assert (tags.title, tags.artist, tags.albumartist, tags.album) == ("Sång Ä", "Artist", "Band", "Album")
    assert (tags.track, tags.discnumber, tags.year, tags.composer, tags.genre) == ("3", "2", "1980-07-11", "Writer", "New Wave")
    assert tags.duration_seconds and 0.5 < tags.duration_seconds <= SECONDS + 0.1


@pytest.mark.parametrize("ext", FORMATS)
def test_an_untagged_file_has_empty_fields_and_no_error(tmp_path, ext):
    tags = read_tags(make_audio(tmp_path / f"blank{ext}"))
    assert tags.load_error == "" and tags.title == "" and tags.track == ""


def test_a_damaged_file_is_said_not_raised(tmp_path):
    bad = tmp_path / "bad.flac"
    bad.write_bytes(b"not a flac at all")
    tags = read_tags(bad)
    assert tags.load_error and tags.title == ""
    assert read_cover(bad) is None


def test_an_mp3_with_damaged_audio_still_gives_its_id3_tags(tmp_path):
    from mutagen.id3 import ID3, TIT2

    path = tmp_path / "broken.mp3"
    path.write_bytes(b"")
    tags = ID3()
    tags.add(TIT2(encoding=3, text="Still Here"))
    tags.save(path)
    with open(path, "ab") as handle:
        handle.write(b"garbage, no MPEG frames")
    read = read_tags(path)
    assert read.title == "Still Here" and read.load_error == ""


@pytest.mark.parametrize("ext", FORMATS)
def test_the_front_cover_is_read_from_every_format(tmp_path, ext):
    path = make_audio(tmp_path / f"c{ext}", "x")
    assert read_cover(path) is None
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    embed_cover(path, jpeg)
    data, mime = read_cover(path)
    assert data == jpeg and mime == "image/jpeg"


def test_load_files_keeps_the_order(tmp_path):
    paths = [make_audio(tmp_path / f"{n}{ext}", f"T{n}") for n, ext in enumerate(FORMATS)]
    assert [t.title for t in load_files(paths)] == [f"T{n}" for n in range(len(FORMATS))]


def test_which_names_are_music():
    assert {".mp3", ".flac", ".m4a", ".ogg", ".opus"} <= AUDIO_EXTENSIONS
    assert is_audio_name("01 Song.FLAC") and is_audio_name("a.Opus") and is_audio_name("x.oga")
    assert not any(is_audio_name(n) for n in ("cover.jpg", "album.md", "a.wav.txt", "notes.nfo", "a.m3u"))
