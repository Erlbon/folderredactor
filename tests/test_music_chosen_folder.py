"""The folder you CHOOSE gets its own note when it is eligible: choosing 'Ska' gives Ska/about.md (genre notes ticked), choosing an
artist folder gives artist.md, an album folder album.md. A generic place name (Music, Bands...) or an alphabetical grouping
gives the clear message, not 'no artist or album folders found'. Real engine, counted requests and tag reads, real dialog."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music.flow import Fetchers, NotesEngine, build_proposals, scan, write_proposal  # noqa: E402
from core.music.local import LIBRARY_ROOT_MESSAGE  # noqa: E402
from tests.music_helpers import make_mp3, ultravox_fetchers, ultravox_library  # noqa: E402


def targets_of(folder, kinds):
    return [(t.kind, t.folder.name) for t in scan([folder], kinds=kinds).targets]






def test_a_chosen_artist_folder_gets_its_artist_note_and_an_album_folder_its_album_note(tmp_path):
    artist = ultravox_library(tmp_path)
    assert targets_of(artist, ("artist",)) == [("artist", "Ultravox")]
    assert sorted(targets_of(artist, ("artist", "album"))) == [("album", "Quartet (1982)"), ("album", "Vienna (1980)"), ("artist", "Ultravox")]
    assert targets_of(artist / "Vienna (1980)", ("album",)) == [("album", "Vienna (1980)")]
    assert targets_of(artist, ("genre",)) == []  # genre notes only for a folder that holds artist folders


def test_a_chosen_folder_that_holds_artists_gets_a_genre_note_unless_its_name_is_generic(tmp_path):
    for name in ("Rock", "Music", "Bands", "Artists", "Downloads", "780 - Music", "0 - Bands", "Library", "Media"):
        make_mp3(tmp_path / name / "Some Artist" / "Album (2000)" / "01 a.mp3", "a", "Some Artist", "Album", 1, "2000")
    eligible = {name: targets_of(tmp_path / name, ("genre",)) for name in os.listdir(tmp_path)}
    assert eligible["Rock"] == [("genre", "Rock")]
    assert all(v == [] for k, v in eligible.items() if k != "Rock"), eligible






