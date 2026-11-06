"""Folder notes: the LEVELS (genre / collection / artist / album) and the artist test (core/music/level.py), on real
small trees with tagged music files. The engine runs of mp3redactor's file (a proposal per level, with faked lookups) come
with the engine, plan step 8."""

from core.music.level import artist_key, is_soundtrack_like, names_agree, split_collab, work_title
from core.music.local import ALL_KINDS, scan
from tests.music_helpers import make_audio, make_mp3, ultravox_library


def level_targets(root, **kw):
    return {(t.kind, t.folder.name): t for t in scan([root], kinds=ALL_KINDS, **kw).targets}


# -- the pure parts ----------------------------------------------------------------------------------------------

def test_name_keys_and_collaborations():
    assert artist_key("The Icicle Works") == artist_key("Icicle Works")
    assert artist_key("Simon & Garfunkel") == artist_key("Simon and Garfunkel")
    assert artist_key("Ultravox feat. Someone") == artist_key("Ultravox")
    assert split_collab("A & B") == ["A", "B"] and split_collab("A feat. B") == ["A", "B"] and split_collab("Solo") == ["Solo"]
    assert names_agree("Ultravox & Friends", "Ultravox") and not names_agree("Ultravox", "Queen")


def test_soundtrack_detection_and_work_title():
    assert is_soundtrack_like("Blade Runner (Original Motion Picture Soundtrack)", [])
    assert is_soundtrack_like("Doom", ["Soundtrack"]) and is_soundtrack_like("Pulp Fiction", [], "Soundtracks")
    assert not is_soundtrack_like("Vienna", ["New Wave"])
    assert work_title("Blade Runner (Original Motion Picture Soundtrack)") == "Blade Runner"
    assert work_title("Doom OST") == "Doom" and work_title("Inception") == "Inception"


# -- Genre / Artist / Album ----------------------------------------------------------------------------------------

def test_three_level_tree_has_genre_artist_and_album_targets_and_no_note_for_the_library_root(tmp_path):
    ultravox_library(tmp_path / "Music" / "New Wave")
    found = level_targets(tmp_path / "Music")
    assert sorted(found) == [("album", "Quartet (1982)"), ("album", "Vienna (1980)"), ("artist", "Ultravox"), ("genre", "New Wave")]
    assert found[("genre", "New Wave")].note_file_name == "about.md"
    assert ("genre", "Music") not in found  # the folder the scan started from is the library root


def test_two_level_tree_has_no_genre_level(tmp_path):
    ultravox_library(tmp_path / "Music")
    found = level_targets(tmp_path / "Music")
    assert sorted(found) == [("album", "Quartet (1982)"), ("album", "Vienna (1980)"), ("artist", "Ultravox")]


def test_the_levels_are_the_same_whatever_the_format_of_the_files(tmp_path):
    """A FLAC artist beside an MP3 one and an M4A / Ogg one: the depth of the music files decides, not their format."""
    root = tmp_path / "Music" / "Synth"
    make_audio(root / "Kraftwerk" / "Computer World (1981)" / "01 Pocket Calculator.flac", "Pocket Calculator", "Kraftwerk")
    make_audio(root / "Yello" / "Stella (1985)" / "01 Desire.m4a", "Desire", "Yello")
    make_audio(root / "Yello" / "One Second (1987)" / "01 Moon on Ice.ogg", "Moon on Ice", "Yello")
    make_audio(root / "Sparks" / "Lil' Beethoven (2002)" / "01 The Rhythm Thief.opus", "The Rhythm Thief", "Sparks")
    found = level_targets(tmp_path / "Music")
    assert sorted(found) == [
        ("album", "Computer World (1981)"), ("album", "Lil' Beethoven (2002)"), ("album", "One Second (1987)"),
        ("album", "Stella (1985)"), ("artist", "Kraftwerk"), ("artist", "Sparks"), ("artist", "Yello"), ("genre", "Synth")]


def test_underscore_folder_is_a_grouping_at_the_about_level(tmp_path):
    make_mp3(tmp_path / "Lib" / "_Crossovers" / "Odd Album (2001)" / "01 a.mp3", "a", "Someone", "Odd Album")
    found = level_targets(tmp_path / "Lib")
    assert ("genre", "_Crossovers") in found and ("album", "Odd Album (2001)") in found
    assert found[("genre", "_Crossovers")].note_file_name == "about.md"


# -- collections: Various Artists ----------------------------------------------------------------------------------

def test_various_artists_album_gets_album_md_and_its_container_never_artist_md(tmp_path):
    base = tmp_path / "Various Artists"
    make_mp3(base / "Now 1 (1983)" / "01 a.mp3", "a", "X", "Now 1", 1, "1983", albumartist="Various Artists")
    found = level_targets(tmp_path)
    assert ("artist", "Various Artists") not in found and ("genre", "Various Artists") in found
    assert ("album", "Now 1 (1983)") in found
    # a collection name decides before any tag: even tagged as one artist it is not an artist folder
    make_mp3(tmp_path / "VA" / "Solo (2000)" / "01 a.mp3", "a", "VA", "Solo", 1, "2000")
    assert ("artist", "VA") not in level_targets(tmp_path)
