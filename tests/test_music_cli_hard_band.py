"""Bands the name search cannot find: the Russian band Leningrad (MusicBrainz and Discogs call it 'Ленинград'; a name search for
'Leningrad' returns Leningrad Cowboys and not the band). Wikipedia first (the article's Wikidata item names the MusicBrainz and
Discogs ids), the local album titles (any script), the alias / sort-name search, and 'Look up by link'. Recorded-shape fixtures
(tests/fixtures/notes/leningrad.json), counted requests."""

import json
import os
import re
from pathlib import Path
from urllib.parse import quote

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from redactor_common.core.lookups.discogs import DiscogsClient  # noqa: E402
from core.music.flow import Confidence, Fetchers, NotesEngine, build_proposals, scan  # noqa: E402
from core.music.link import LinkError, parse_link  # noqa: E402
from core.music.local import fold_name  # noqa: E402
from redactor_common.core.lookup_client import Throttle  # noqa: E402
from redactor_common.core.notes import parse_front_matter  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402

FX = json.loads((Path(__file__).parent / "fixtures" / "notes" / "leningrad.json").read_text(encoding="utf-8"))
MBID, COWBOYS = FX["mbid"], FX["cowboys"]
DACHNIKI, PIRATES = "Дачники", "Пираты XXI века"


def quoted(text):
    return re.escape(quote(f'"{text}"', safe=""))


def band_library(root, tag_artist="Leningrad", albums=(DACHNIKI,), folder="Leningrad"):
    years = {DACHNIKI: "2000", PIRATES: "2001"}
    for album in albums:
        make_mp3(root / folder / f"{album} ({years[album]})" / "01 a.mp3", "a", tag_artist, album, 1, years[album])
    return root


def mb_fetch(cyrillic_search=False, titles=True):
    routes = []
    if cyrillic_search:
        routes.append((r"ws/2/artist\?query=artist%3A" + quoted("Ленинград"), FX["search_cyrillic"]))
    routes += [
        (r"ws/2/artist\?query=artist%3A%22Leningrad%22", FX["search_latin"]),
        (r"ws/2/artist\?query", {"artists": []}),
        (r"ws/2/artist/" + MBID, FX["artist"]),
        (r"ws/2/artist/" + COWBOYS, {"id": COWBOYS, "name": "Leningrad Cowboys", "sort-name": "Leningrad Cowboys", "type": "Group",
                                    "country": "FI", "life-span": {"begin": "1986"}, "relations": []}),
        (r"ws/2/release-group\?artist=" + MBID, FX["release_groups_band"]),
        (r"ws/2/release-group\?artist=" + COWBOYS, FX["release_groups_cowboys"]),
        (r"ws/2/release-group\?artist=", {"release-groups": []}),
        (r"ws/2/artist/", {"id": "x", "name": "x", "relations": []}),
    ]
    if titles:
        routes += [(r"ws/2/release-group\?query=releasegroup%3A" + quoted(DACHNIKI), FX["title_search_dachniki"]),
                   (r"ws/2/release-group\?query=releasegroup%3A" + quoted(PIRATES), FX["title_search_pirates"])]
    routes.append((r"ws/2/release-group\?query", {"release-groups": []}))
    return FakeFetch(routes)


def wiki_fetch(article=True):
    routes = []
    if article:
        routes += [(r"page/summary/Leningrad_\(band\)$", FX["wikipedia_summary"]),
                   (r"wikidata\.org.*titles=Leningrad", FX["wikidata_claims"]),
                   (r"wikidata\.org.*ids=Q909810", FX["wikidata_claims"])]
    routes += [(r"wikidata\.org", FX["wikidata_missing"]), (r"search/title", {"pages": []}), (r"page/summary/", None)]
    return FakeFetch(routes)


def discogs_client():
    fake = FakeFetch([
        (r"database/search\?type=artist", FX["discogs_search_latin"]),
        (r"database/search", {"results": []}),
        (r"artists/111/releases", FX["discogs_releases_cowboys"]),
        (r"artists/222/releases", FX["discogs_releases_orchestra"]),
        (r"artists/331797/releases", FX["discogs_releases_band"]),
        (r"artists/331797", FX["discogs_artist_band"]),
        (r"artists/111", {"id": 111, "name": "Leningrad Cowboys"}),
        (r"artists/222", {"id": 222, "name": "Leningrad Philharmonic Orchestra"}),
    ])
    return DiscogsClient("t", fetch=fake, throttle=Throttle(0))


def run(root, fetchers, name="Leningrad", **engine_kwargs):
    engine = NotesEngine(fetchers, **engine_kwargs)
    target = next(t for t in scan([root], kinds=("artist",)).targets if t.folder.name == name)
    [proposal] = build_proposals([target], engine=engine)
    return proposal, engine


# -- the Cyrillic titles are comparable -------------------------------------------------------------------------------



# -- 1. Wikipedia first ---------------------------------------------------------------------------------------------------









# -- 2. the local album titles ---------------------------------------------------------------------------------------------







# -- 3. spelling, alias, sort name ------------------------------------------------------------------------------------------





# -- the links ------------------------------------------------------------------------------------------------------------------







def uncertain_cowboys(tmp_path, **fetch_kwargs):
    band_library(tmp_path, albums=(PIRATES,))
    mb, wiki = mb_fetch(titles=False), wiki_fetch(article=False)
    engine = NotesEngine(Fetchers(mb=mb, wiki=wiki, **fetch_kwargs))
    target = next(t for t in scan([tmp_path], kinds=("artist",)).targets)
    [proposal] = build_proposals([target], engine=engine)
    assert proposal.confidence == Confidence.UNCERTAIN
    return proposal, engine, mb, wiki













# -- the review page ---------------------------------------------------------------------------------------------------------



# -- the command line --------------------------------------------------------------------------------------------------------

def test_cli_link_gives_a_folder_the_page_and_checks_the_link(tmp_path, monkeypatch, capsys):
    from foldercli import cmd_notes
    from foldercli.main import main
    from redactor_common.cli import CliError

    pass  # the conftest isolates the settings
    band_library(tmp_path, albums=(PIRATES,))
    mb, wiki = mb_fetch(titles=False), wiki_fetch(article=False)
    wiki.routes.insert(0, (r"wikidata\.org.*ids=Q909810", FX["wikidata_claims"]))
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: Fetchers(mb=mb, wiki=wiki))
    code = main(["notes", str(tmp_path), "--kind", "artist", "--write", "--no-cache", "--json",
                 "--link", "Leningrad=https://www.wikidata.org/wiki/Q909810"])
    document = json.loads(capsys.readouterr().out)
    assert code == 0 and [r["status"] for r in document["results"]] == ["written"]
    written = (tmp_path / "Leningrad" / "artist.md").read_text(encoding="utf-8")
    assert "title: Leningrad" in written and "musicbrainz.org" in written
    with pytest.raises(CliError):
        main(["notes", str(tmp_path), "--kind", "artist", "--link", "Leningrad=https://evil.example/x"])
    with pytest.raises(CliError):
        main(["notes", str(tmp_path), "--kind", "artist", "--link", "no equals sign"])
