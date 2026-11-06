"""'What to create' as checkboxes: ticking only 'Genre / collection notes' looks up nothing about artists or albums and reads no
tags (only the folder structure is walked, then about one Wikipedia lookup per genre folder). Real scope dialog (offscreen,
QTest), the real engine, counted fetcher calls and counted tag reads."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music import tags as music_tags  # noqa: E402
from core.music.flow import Fetchers, NotesEngine, build_proposals, scan  # noqa: E402
from core.music.kinds import kinds_text, parse_kinds  # noqa: E402
from core.music.timing import scope_hint  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402


def ska_tree(root):
    """Bands/Ska/<3 artists>/<2 albums each>, and Bands/D/<an artist>/<an album>: an alphabetical grouping."""
    for artist in ("Specials", "Madness", "Selecter"):
        for album in ("First (1979)", "Second (1980)"):
            make_mp3(root / "Bands" / "Ska" / artist / album / "01 a.mp3", "a", artist, album.split(" (")[0], 1, album[-5:-1])
    make_mp3(root / "Bands" / "D" / "Dub Band" / "Only (1990)" / "01 a.mp3", "a", "Dub Band", "Only", 1, "1990")
    return root / "Bands"


def genre_wiki():
    return FakeFetch([
        (r"search/title\?q=Ska", {"pages": [{"title": "Ska", "description": "Music genre",
                                             "excerpt": "Ska is a music genre that originated in Jamaica"}]}),
        (r"search/title", {"pages": []}),
        (r"page/summary/Ska$", {"type": "standard", "title": "Ska", "description": "Music genre",
                                "extract": "Ska is a music genre that originated in Jamaica in the late 1950s.",
                                "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Ska"}}}),
        (r"page/summary/", None),
    ])


def nothing_else():
    """MusicBrainz and Discogs that fail the test if they are asked anything."""
    def boom(request):
        raise AssertionError(f"an artist / album lookup was made: {request}")

    return boom


class TagReads:
    def __init__(self, monkeypatch):
        self.count = 0
        real = music_tags.read_tags  # load_files reads every file through it

        def counting(path, *a, **k):
            self.count += 1
            return real(path, *a, **k)

        monkeypatch.setattr(music_tags, "read_tags", counting)


# -- the words ----------------------------------------------------------------------------------------------------

def test_kinds_are_parsed_and_the_old_words_still_work():
    assert parse_kinds("artist,genre") == ("artist", "genre") and parse_kinds("genre") == ("genre",)
    assert parse_kinds("both") == ("artist", "album") and parse_kinds("all") == ("artist", "album", "genre")
    assert parse_kinds(("genre", "artist")) == ("artist", "genre") and parse_kinds("") == ("artist",)
    assert parse_kinds("nonsense") == ("artist",) and kinds_text(("album", "artist")) == "artist,album"
    # (the review page's 'Looked up: ...' sentence for these kinds is tested with the music review page, plan step 9)


def test_the_hint_for_genre_only_says_how_many_folders_and_how_long():
    assert scope_hint(500, 900, 4, "genre") == "About 4 genre / collection folders: about 2 s (one Wikipedia lookup each, no tags read)."
    assert scope_hint(500, 900, 1, "genre").startswith("About 1 genre / collection folder: about 1 s")
    assert scope_hint(500, 900, 0, "genre") == ""
    assert "artist notes only is about" in scope_hint(300, 400, 0, "artist,album")  # unchanged for album notes


# -- the engine ---------------------------------------------------------------------------------------------------

def test_genre_only_on_the_parent_makes_only_wikipedia_requests_and_reads_no_tags(tmp_path, monkeypatch):
    bands = ska_tree(tmp_path)
    reads = TagReads(monkeypatch)
    wiki = genre_wiki()
    fetchers = Fetchers(mb=nothing_else(), wiki=wiki)
    found = scan([bands], kinds=("genre",))
    assert [(t.kind, t.folder.name) for t in found.targets] == [("genre", "Ska")]  # D is a grouping, Bands the root
    assert [g.folder.name for g in found.groupings] == ["D"]
    engine = NotesEngine(fetchers)
    [proposal] = build_proposals(found.targets, engine=engine)
    assert proposal.confidence.value == "confident" and proposal.note_kind == "about" and "Jamaica" in proposal.note_text
    assert len(wiki.urls) == 2  # the search and the summary: about one Wikipedia lookup for the folder
    assert reads.count == 0 and engine.phases.count("tags") == 0 and engine.phases.count("musicbrainz") == 0




# -- the real scope dialog ----------------------------------------------------------------------------------------



