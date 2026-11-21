"""Folder names that end in a dot ('R.E.M.', 'Tolkien, J.R.R.'): an ordinary Windows path to one drops the dot and finds
nothing (core/long_paths.py). The music and video scans read them now, as the book and comic scans and the tree do."""

import os
from pathlib import Path

import pytest

from redactor_common.core.long_paths import literal, needs_literal
from core.music.local import scan as music_scan
from core.video.local import scan as video_scan
from tests.music_helpers import make_audio
from tests.notes_gui_helpers import boxes  # noqa: F401 -- a fixture
from tests.video_helpers import make_movie


def mkdirs(path: Path) -> Path:
    os.makedirs(literal(path), exist_ok=True)
    return path


def note(folder: Path, name: str) -> None:
    with open(literal(folder / name), "w", encoding="utf-8") as handle:
        handle.write(f"# {folder.name}\n")


def audio(stage: Path, path: Path, *tags) -> None:
    """make_audio into a folder that may end in a dot: built in the plain folder `stage`, then moved in by its literal path."""
    plain = stage / path.name
    make_audio(plain, *tags)
    mkdirs(path.parent)
    os.replace(literal(plain), literal(path))


@pytest.mark.skipif(os.name != "nt", reason="the dot is only dropped on Windows")
def test_literal_only_where_a_name_ends_in_a_dot(tmp_path):
    assert literal(tmp_path / "R.E.M.").startswith("\\\\?\\") and not needs_literal(tmp_path / "Ultravox")
    assert literal(tmp_path / "Ultravox") == str(tmp_path / "Ultravox")
    assert literal(r"\\server\share\R.E.M.") == "\\\\?\\UNC\\server\\share\\R.E.M."


def test_the_music_scan_finds_an_artist_whose_name_ends_in_a_dot_and_its_note(tmp_path):
    lib = mkdirs(tmp_path / "Music")
    stage = tmp_path / "_plain"
    audio(stage, lib / "R.E.M." / "Murmur (1983)" / "01 Radio Free Europe.mp3", "Radio Free Europe", "R.E.M.", "Murmur", 1,
          "1983")
    audio(stage, lib / "Guns N' Roses" / "G N' R Lies." / "01 Patience.mp3", "Patience", "Guns N' Roses", "G N' R Lies", 1,
          "1988")
    note(lib / "R.E.M.", "artist.md")
    result = music_scan([lib], kinds=("artist", "album"))
    left = {t.folder.name for t in result.targets}
    have = {s.folder.name for s in result.skipped if s.reason.startswith("already has")}
    assert left == {"Murmur (1983)", "Guns N' Roses", "G N' R Lies."} and have == {"R.E.M."}
    for t in result.targets:  # plain paths with the dot kept (the tree compares them), and real folders
        assert not str(t.folder).startswith("\\\\?\\") and os.path.isdir(literal(t.folder))
    assert music_scan([lib / "R.E.M."], kinds=("artist",)).skipped  # chosen on its own, too


def test_look_up_reads_the_tags_and_writes_the_notes_in_a_folder_whose_name_ends_in_a_dot(window, tmp_path, boxes):
    """The whole way: scan, the tags and the cover read, the draft built, both notes written (redactor_common 2026-11-21)."""
    from tests.music_helpers import embed_cover, ultravox_fetchers, ultravox_library
    from tests.notes_gui_helpers import look_up, pump

    stage = tmp_path / "stage"
    stage.mkdir()
    plain = ultravox_library(stage, with_quartet=False)
    embed_cover(next((plain / "Vienna (1980)").glob("*.mp3")), b"\xff\xd8\xff\xe0" + b"0" * 64)
    lib = mkdirs(tmp_path / "Library")
    artist = lib / "Ultravox."
    os.replace(literal(plain), literal(artist))
    album = artist / "Vienna (1980)"
    look_up(window, lib, ultravox_fetchers(), kinds=("artist", "album"))
    draft = window.item_of(str(album))
    assert draft is not None and draft.proposal.writable, "the album was drafted from its tags"
    assert window.item_of(str(artist)).proposal.writable
    window._on_write_ticked()
    pump(lambda: window.tree.note_state(str(album))[1] != "", "the written notes")
    assert os.path.isfile(literal(artist / "artist.md")) and os.path.isfile(literal(album / "album.md"))
    assert "Wrote 2 notes." in window.status_bar.currentMessage()


def test_the_video_scan_finds_a_film_whose_folder_ends_in_a_dot(tmp_path):
    lib = mkdirs(tmp_path / "Video")
    plain = make_movie(tmp_path / "_plain", "Mr. Smith Goes to Washington (1939)", "Mr.Smith.Goes.to.Washington.1939.mkv")
    target = lib / "Mr. Smith Goes to Washington (1939) Dir. Capra."
    os.replace(literal(plain), literal(target))
    result = video_scan([lib])
    assert [t.folder.name for t in result.targets] == [target.name]
