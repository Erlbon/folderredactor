"""Level rules from Scan on Erlend's real share (0 - Bands R, Q, B, I, Y; 2026-11-21), decisions 1A, 2C, 3B and 4B."""

from core.music.local import (
    ALL_KINDS, GROUPING_REASON, SORTING_REASON, album_files, album_folder_of, classify, folder_layout, scan,
)
from tests.music_helpers import make_mp3


def song(folder, name="01 a.mp3"):
    return make_mp3(folder / name, "a", "Band", "Album", 1, "2000")


def kinds(found):
    """The targets below the folder scanned (pytest's own folder above them would be a genre)."""
    return sorted((t.kind, t.folder.relative_to(found_root[0]).as_posix()) for t in found.targets if t.folder != found_root[0])


found_root = [None]


def scan_tree(root, start=None):
    found_root[0] = root
    return scan([start or root], kinds=ALL_KINDS)


def letter_r(root):
    """0 - Bands/R as on the share: real artists with year albums, and a band with its songs loose."""
    bands = root / "0 - Bands"
    song(bands / "R" / "Radiohead" / "[1997] - OK Computer")
    song(bands / "R" / "Radiohead" / "[2000] - Kid A")
    song(bands / "R" / "Ramones, The" / "[1976] - Ramones")
    song(bands / "R" / "Rammsund", "01 - Du duftar godt.mp3")
    song(bands / "R" / "Rammsund", "02 - Eg vil.mp3")
    return bands


# 1A ----------------------------------------------------------------------------------------------------------------------

def test_a_letter_folder_scanned_from_itself_is_a_grouping_not_an_artist(tmp_path):
    bands = letter_r(tmp_path)
    found = scan_tree(bands / "R")
    assert "." not in [t.folder.relative_to(bands / "R").as_posix() for t in found.targets]
    assert [(g.folder.name, g.reason) for g in found.groupings] == [("R", GROUPING_REASON)]


def test_a_letter_with_a_loose_band_still_gives_the_letter_layout(tmp_path):
    bands = letter_r(tmp_path)
    assert classify(bands / "R") == ""
    assert folder_layout(bands) == "letter/artist/album"


def test_a_band_called_x_that_holds_its_albums_is_still_an_artist(tmp_path):
    song(tmp_path / "X" / "[2001] - Album One")
    song(tmp_path / "X" / "[2003] - Album Two")
    assert classify(tmp_path / "X") == "artist"


# 2C ----------------------------------------------------------------------------------------------------------------------

def test_a_year_album_with_a_bonus_disc_is_one_album(tmp_path):
    album = tmp_path / "REM (1980 - 2011)" / "[2006] - And I Feel Fine The Best of the IRS Years 1982-1987"
    song(album)
    bonus = song(album / "Bonus Disc")
    song(tmp_path / "REM (1980 - 2011)" / "[1983] - Murmur")
    assert classify(album) == "album" and classify(album.parent) == "artist"
    assert album_folder_of(bonus) == album and bonus in album_files(album)


def test_a_year_album_whose_only_subfolder_holds_the_songs_is_one_album(tmp_path):
    album = tmp_path / "Rammstein" / "[2020] - Remixes"
    track = song(album / "Remixes")
    song(tmp_path / "Rammstein" / "[1995] - Herzeleid")
    found = scan_tree(tmp_path)
    assert kinds(found) == [("album", "Rammstein/[1995] - Herzeleid"), ("album", "Rammstein/[2020] - Remixes"),
                            ("artist", "Rammstein")]
    assert album_folder_of(track) == album


def test_a_year_album_with_named_volumes_or_dates_is_one_album(tmp_path):
    song(tmp_path / "Bauhaus" / "[1986] - Best Of Bauhaus - Volume 1 & 2" / "1979-1983 Volume One")
    song(tmp_path / "Bauhaus" / "[1986] - Best Of Bauhaus - Volume 1 & 2" / "1979-1983 Volume Two")
    song(tmp_path / "Bauhaus" / "[1980] - In the Flat Field")
    song(tmp_path / "Yeah Yeah Yeahs" / "[2004] - Live at the Fillmore" / "Live at the Fillmore March 16 2004")
    song(tmp_path / "Yeah Yeah Yeahs" / "[2004] - Live at the Fillmore" / "Live at the Fillmore March 17 2004")
    song(tmp_path / "Yeah Yeah Yeahs" / "[2003] - Fever to Tell")
    found = scan_tree(tmp_path)
    assert kinds(found) == [
        ("album", "Bauhaus/[1980] - In the Flat Field"), ("album", "Bauhaus/[1986] - Best Of Bauhaus - Volume 1 & 2"),
        ("album", "Yeah Yeah Yeahs/[2003] - Fever to Tell"), ("album", "Yeah Yeah Yeahs/[2004] - Live at the Fillmore"),
        ("artist", "Bauhaus"), ("artist", "Yeah Yeah Yeahs")]


def test_dated_year_names_count_too(tmp_path):
    for name in ("[2004.04.20] - Ratatat", "[2018-03-02] - New Worlds", "[1994]  -Give It Away"):
        song(tmp_path / name / "Disc A")
        assert classify(tmp_path / name) == "album", name


def test_without_a_year_the_album_name_with_a_number_is_a_disc(tmp_path):
    box = tmp_path / "Way Hap Ultimate Rarities"
    song(box / "Way Hap Ultimate Rarities 1")
    song(box / "Way Hap Ultimate Rarities 2")
    assert classify(box) == "album"


def test_without_a_year_wide_disc_names_need_every_music_subfolder_to_be_disc_like(tmp_path):
    """An artist with 'Greatest Hits Vol. 2' next to other albums stays an artist: the volume is an album of its own."""
    artist = tmp_path / "Band"
    song(artist / "Greatest Hits Vol. 2")
    song(artist / "Another Album")
    assert classify(artist) == "artist"


# 3B ----------------------------------------------------------------------------------------------------------------------

def test_sorting_folders_inside_an_artist_get_no_note_and_their_albums_are_albums(tmp_path):
    artist = tmp_path / "Big Black"  # on the share: 18 albums next to its two sorting folders
    song(artist / "[1986] - Atomizer")
    song(artist / "[1987] - Songs About Fucking")
    song(artist / "[1983] - Bulldozer")
    song(artist / "Bootlegs" / "[1987] - Peel Session [7 in - Bootleg]")
    song(artist / "Bootlegs" / "[1991] - Kerosene [LP - Bootleg]")
    song(artist / "Rare Stuff" / "Big Black Rarities")
    song(artist / "Rare Stuff" / "Way Hap Ultimate Rarities" / "Way Hap Ultimate Rarities 1")
    song(artist / "Rare Stuff" / "Way Hap Ultimate Rarities" / "Way Hap Ultimate Rarities 2")
    found = scan_tree(tmp_path)
    assert kinds(found) == [
        ("album", "Big Black/Bootlegs/[1987] - Peel Session [7 in - Bootleg]"),
        ("album", "Big Black/Bootlegs/[1991] - Kerosene [LP - Bootleg]"),
        ("album", "Big Black/Rare Stuff/Big Black Rarities"),
        ("album", "Big Black/Rare Stuff/Way Hap Ultimate Rarities"),
        ("album", "Big Black/[1983] - Bulldozer"), ("album", "Big Black/[1986] - Atomizer"),
        ("album", "Big Black/[1987] - Songs About Fucking"), ("artist", "Big Black")]
    assert sorted((s.folder.name, s.reason) for s in found.skipped) == [
        ("Bootlegs", SORTING_REASON), ("Rare Stuff", SORTING_REASON)]


def test_singles_inside_an_artist_is_a_sorting_folder(tmp_path):
    song(tmp_path / "Beautiful South, The" / "[1989] - Welcome to the Beautiful South")
    song(tmp_path / "Beautiful South, The" / "Singles" / "[1994] - Good As Gold (CD2)")
    found = scan_tree(tmp_path)
    assert ("album", "Beautiful South, The/Singles/[1994] - Good As Gold (CD2)") in kinds(found)
    assert [(s.folder.name, s.reason) for s in found.skipped] == [("Singles", SORTING_REASON)]


# 4B ----------------------------------------------------------------------------------------------------------------------

def test_a_band_with_its_songs_loose_under_a_letter_is_an_artist(tmp_path):
    bands = letter_r(tmp_path)
    found = scan_tree(bands)
    assert ("artist", "R/Rammsund") in kinds(found) and ("album", "R/Rammsund") not in kinds(found)
    assert ("artist", "R/Radiohead") in kinds(found)


def test_a_folder_of_bands_with_one_loose_band_is_not_an_artist(tmp_path):
    """Found while building: 'Rock' holding two bands and one band with its songs loose looked like an artist, and 3B then
    skipped the two real bands as its sorting folders."""
    song(tmp_path / "Rock" / "Band One" / "[1990] - First")
    song(tmp_path / "Rock" / "Band Two" / "[1991] - Second")
    song(tmp_path / "Rock" / "Loose Band")
    assert classify(tmp_path / "Rock") == ""
    found = scan_tree(tmp_path)
    assert ("artist", "Rock/Band One") in kinds(found) and ("artist", "Rock/Band Two") in kinds(found)
    assert not found.skipped


def test_an_artist_with_loose_singles_next_to_albums_is_not_an_album_of_the_folder_above(tmp_path):
    song(tmp_path / "Rock" / "Ultravox" / "[1980] - Vienna")
    song(tmp_path / "Rock" / "Ultravox" / "[1982] - Quartet")
    song(tmp_path / "Rock" / "Ultravox", "Dancing With Tears in My Eyes.mp3")
    assert classify(tmp_path / "Rock") == ""
    assert ("artist", "Rock/Ultravox") in kinds(scan_tree(tmp_path))


def test_loose_songs_outside_a_letter_are_still_an_album(tmp_path):
    song(tmp_path / "Rock" / "Some Band" / "Some Album")
    song(tmp_path / "Rock" / "Some Band" / "Other Album")
    song(tmp_path / "Rock" / "Loose Record")
    found = scan_tree(tmp_path)
    assert ("album", "Rock/Loose Record") in kinds(found)
