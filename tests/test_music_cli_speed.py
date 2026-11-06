"""Create Notes speed, round two: where the time goes (phases), Discogs asked as a fallback (or side by side with MusicBrainz),
a sample of the tags instead of all of them, tags read by a small pool, singles optional, and a busy MusicBrainz announced.
Counted calls, not stubs: the injected fetchers and loaders count what really reaches them."""

import json
import threading
import time
from pathlib import Path

import pytest

from core.music import local as notes_local
from core.music.flow import Fetchers, NotesEngine, build_proposals, scan
from core.music.local import KIND_ARTIST, read_artist
from core.music.phases import PhaseTimer, mmss
from tests.music_helpers import FakeFetch, make_mp3, ultravox_fetchers, ultravox_library, cristina_fetchers, cristina_library
from tests.test_music_sources import artist_routes, discogs, no_mb, no_wiki


def artist_target(root, name="Ultravox"):
    return next(t for t in scan([root], kinds=(KIND_ARTIST,)).targets if t.folder.name == name)


def discogs_requests(fetchers) -> int:
    return len(fetchers.discogs._fetch.urls)


def with_discogs(base: Fetchers) -> Fetchers:
    base.discogs = discogs(*artist_routes())
    return base


# -- the phases ----------------------------------------------------------------------------------------------------





# -- Discogs: a fallback by default --------------------------------------------------------------------------------











# -- the tags: a sample, then all if unsure; a small pool ------------------------------------------------------------

def many_albums(root, albums=6, files=8, artist="Ultravox"):
    base = root / artist
    for a in range(albums):
        for f in range(files):
            make_mp3(base / f"Album {a} ({1980 + a})" / f"{f + 1:02d} t.mp3", f"t{f}", artist, f"Album {a}", f + 1, str(1980 + a))
    return base


class CountingLoader:
    def __init__(self):
        self.files, self.calls = [], 0

    def __call__(self, paths):
        self.calls += 1
        self.files += [Path(p).name for p in paths]
        return notes_local.default_loader(paths)












# -- singles ---------------------------------------------------------------------------------------------------------



# -- the command line -------------------------------------------------------------------------------------------------

@pytest.fixture
def cli(monkeypatch, capsys):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    state = {}

    def run(*argv):
        state["fetchers"] = with_discogs(ultravox_fetchers())
        monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: state["fetchers"] if use else ultravox_fetchers())
        code = main(["notes", *argv, "--json", "--no-cache"])
        captured = capsys.readouterr()
        return code, json.loads(captured.out), captured.err, state["fetchers"]

    return run


def test_cli_discogs_modes_and_the_phase_summary(tmp_path, cli):
    ultravox_library(tmp_path)
    code, document, err, fetchers = cli(str(tmp_path))  # the default: fallback
    assert code == 0 and discogs_requests(fetchers) == 0
    assert document["phases"]["tags"]["count"] == 5 and document["phases"]["musicbrainz"]["count"] == 3
    assert "Time: " in err and "Looked up 1 folder in" in err
    _c, _d, _e, always = cli(str(tmp_path), "--discogs", "always")
    assert discogs_requests(always) == 3
    _c, never_document, _e, never = cli(str(tmp_path), "--discogs", "never")
    assert discogs_requests(never) == 0 and "discogs" not in never_document["phases"]
    _c, _d, _e, no_discogs = cli(str(tmp_path), "--no-discogs")
    assert discogs_requests(no_discogs) == 0


def test_cli_no_singles(tmp_path, cli):
    ultravox_library(tmp_path)
    _c, _d, _e, fetchers = cli(str(tmp_path), "--no-singles")
    assert any("type=album%7Cep" in u for u in fetchers.mb.urls)


# -- the window ---------------------------------------------------------------------------------------------------------

