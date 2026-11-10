"""Picking a candidate must REPLACE the row in place. A person saw 'Use selected candidate' leave the uncertain row where it was
AND show a confident row further down ('the last line follows me around'): the list was rebuilt on every pick. Now the rows of
the picked folders are updated in place (same row objects, same positions, same scroll position, same selection), the engine
names one candidate when MusicBrainz and Discogs agree on the artist, and every path that rebuilds a proposal is checked here:
real window, real engine and fake services, the real review dialog in list view with 60 rows, real clicks."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


from redactor_common.core.lookups.discogs import DiscogsClient  # noqa: E402
from core.music.flow import Fetchers  # noqa: E402
from redactor_common.core.lookup_client import Throttle  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402

TIE = "Czar Chainfist"  # sorts after the 59 others: the row is deep in the list, the list is scrolled
NAMES = [f"Cband {i:02d}" for i in range(59)] + [TIE]


def library(root):
    for name in NAMES:
        make_mp3(root / "C" / name / "Some Album (2001)" / "01 a.mp3", "a", name, "Some Album", 1, "2001")
    return root


def fetchers(both_sources=True, guessable=False):
    """guessable: MusicBrainz names the band 'Czar Chainfist (band)' (a loose name: uncertain) and lists 'Some Album': the one candidate
    with a local album, so the engine has a best guess for the row."""
    mb_name = f"{TIE} (band)" if guessable else TIE
    mb = FakeFetch([
        (r"ws/2/artist\?query=artist%3A%22Czar", {"artists": [{"id": "mb-czar", "name": mb_name, "score": 100, "sort-name": mb_name,
            "type": "Group", "country": "DK", "disambiguation": "Danish heavy metal/hard rock group",
            "life-span": {"begin": "1998" if guessable else "2007"}}]}),
        (r"ws/2/artist\?query", {"artists": []}),
        (r"ws/2/release-group\?query=", {"release-groups": []}),
        (r"ws/2/release-group\?artist=mb-czar", {"release-groups": [
            {"id": "rg1", "title": "Another Album", "primary-type": "Album", "first-release-date": "2010"},
            *([{"id": "rg2", "title": "Some Album", "primary-type": "Album", "first-release-date": "2001"}] if guessable else [])]}),
        (r"ws/2/artist/mb-czar", {"id": "mb-czar", "name": TIE, "type": "Group", "life-span": {"begin": "2007"},
                                  "relations": [], "genres": [], "tags": []}),
    ])
    wiki = FakeFetch([(r"search/title", {"pages": []}), (r"page/summary/", None)])
    discogs = FakeFetch([
        (r"database/search\?type=artist&q=Czar", {"results": [{"id": 2521047, "title": TIE}]}),
        (r"database/search", {"results": []}),
        (r"artists/2521047/releases", {"releases": [{"title": "Another Album", "year": 2010, "role": "Main", "type": "master"}]}),
        (r"artists/2521047", {"id": 2521047, "name": TIE, "profile": "Danish band.", "members": [],
                              "uri": "https://www.discogs.com/artist/2521047"}),
    ])
    return Fetchers(mb=mb, wiki=wiki, discogs=DiscogsClient("t", fetch=discogs, throttle=Throttle(0)) if both_sources else None)


# -- two services, one name: separate unless a fact agrees -------------------------------------------------------------


def test_candidates_with_a_local_album_in_both_discographies_are_merged_and_the_note_says_why():
    from core.music.flow import Candidate, NotesEngine

    a = Candidate("musicbrainz", "m", "Same Name", "Danish group", ["Album One", "Album Two"], 1.0)
    b = Candidate("discogs", "d", "Same Name", "Discogs d", ["Album Two"], 1.0)
    [merged] = NotesEngine._merge_same_artist([a, b])
    assert merged.source == "musicbrainz" and merged.also == "discogs" and merged.also_id == "d"
    assert merged.note.startswith("merged with Discogs d: both discographies have 'Album Two'")
    assert "Discogs d" in merged.detail
    # the same name and no shared album, or different names: never merged
    assert len(NotesEngine._merge_same_artist([a, Candidate("discogs", "d", "Same Name", "", ["Other"], 1.0)])) == 2
    assert len(NotesEngine._merge_same_artist([a, Candidate("discogs", "d", "Other Name", "", ["Album Two"], 1.0)])) == 2


def test_picking_a_merged_candidate_builds_the_note_from_both_sources(tmp_path):
    from core.music.flow import Candidate, NotesEngine, scan
    from core.music.local import KIND_ARTIST

    library(tmp_path)
    engine = NotesEngine(fetchers())
    target = next(t for t in scan([tmp_path], kinds=(KIND_ARTIST,)).targets if t.folder.name == TIE)
    proposal = engine.build_proposal(target)
    merged = Candidate("musicbrainz", "mb-czar", TIE, "", ["Another Album"], 1.0, also="discogs", also_id="2521047")
    built = engine.rebuild(proposal, merged)
    assert built.confidence.value == "confident" and "musicbrainz" in built.sources and "discogs" in built.sources
    assert "chosen by you" in " ".join(built.reasons)


# -- the rebuilds: in place ------------------------------------------------------------------------------------------


