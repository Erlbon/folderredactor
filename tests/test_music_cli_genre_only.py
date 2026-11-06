"""'What to create' as checkboxes: ticking only 'Genre / collection notes' looks up nothing about artists or albums and reads no
tags (only the folder structure is walked, then about one Wikipedia lookup per genre folder). Real scope dialog (offscreen,
QTest), the real engine, counted fetcher calls and counted tag reads."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music import tags as scan_service  # noqa: E402
from core.music.flow import Fetchers, NotesEngine, build_proposals, scan  # noqa: E402
from core.music.kinds import kinds_text, parse_kinds  # noqa: E402
from core.music.timing import scope_hint  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3, set_kinds  # noqa: E402


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
        real = scan_service.read_tags  # load_files reads every file through it

        def counting(path, *a, **k):
            self.count += 1
            return real(path, *a, **k)

        monkeypatch.setattr(scan_service, "read_tags", counting)


# -- the words ----------------------------------------------------------------------------------------------------





# -- the engine ---------------------------------------------------------------------------------------------------



def test_the_command_line_takes_the_same_in_combination(tmp_path, monkeypatch, capsys):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    bands = ska_tree(tmp_path)
    reads = TagReads(monkeypatch)
    wiki = genre_wiki()
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: Fetchers(mb=nothing_else(), wiki=wiki))
    code = main(["notes", str(bands), "--kind", "genre", "--json", "--no-cache"])
    document = json.loads(capsys.readouterr().out)
    assert code == 0 and [r["kind"] for r in document["results"] if r["status"] != "grouping"] == ["genre"]
    assert document["requests"] == 2 and reads.count == 0
    with pytest.raises(SystemExit) as usage:  # argparse: an unknown word is a usage error
        main(["notes", str(bands), "--kind", "bogus"])
    assert usage.value.code == 2
    capsys.readouterr()
    parsed = cmd_notes.kind_argument("artist,genre")
    assert parsed == ("artist", "genre") and cmd_notes.kind_argument("both") == ("artist", "album")


# -- the real scope dialog ----------------------------------------------------------------------------------------



