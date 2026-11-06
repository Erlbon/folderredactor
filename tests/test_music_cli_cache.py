"""Create Notes speed: the request layer (per-run memo + persistent cache), the request counts of the engine, the
'What to create' choice, the CLI's artist-only default and --no-cache. Hit counters, not stubs: the injected fetchers
count what really reaches them."""

import json
import re
import sqlite3
import threading
import urllib.error
import urllib.request

import pytest

from redactor_common.core.lookups.discogs import DiscogsClient
from core.music.cache import (
    CachedDiscogs, CachedFetch, RequestStats, ResponseCache, looks_empty, NEGATIVE_TTL_SECONDS, TTL_SECONDS,
)
from core.music.flow import Confidence, Fetchers, NotesEngine, build_proposals, scan
from core.music.local import KIND_ALBUM, KIND_ARTIST
from redactor_common.core.lookup_client import Throttle
from tests.music_helpers import RECORDED, FakeFetch, ultravox_fetchers, ultravox_library


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture
def cache(tmp_path):
    clock = Clock()
    c = ResponseCache(tmp_path / "cache.sqlite", clock=clock)
    c.clock = clock
    yield c
    c.close()


# -- the disk store ---------------------------------------------------------------------------------------------















# -- the wrappers -------------------------------------------------------------------------------------------------









# -- the engine's request counts --------------------------------------------------------------------------------

def mb_urls(fetchers):
    return fetchers.mb.urls


def patterns(urls, *regexes):
    return {rx: sum(1 for u in urls if re.search(rx, u)) for rx in regexes}














# -- the command line ---------------------------------------------------------------------------------------------

def test_cli_default_kind_is_artist_and_makes_no_album_requests(tmp_path, capsys, monkeypatch):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    fetchers = ultravox_fetchers()
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: fetchers)
    ultravox_library(tmp_path)
    code = main(["notes", str(tmp_path), "--json"])
    document = json.loads(capsys.readouterr().out)
    assert code == 0 and {r["kind"] for r in document["results"]} == {"artist"}
    assert not [u for u in fetchers.mb.urls if re.search(r"release-group/rg-|ws/2/release/", u)]
    assert document["requests"] == 5 and document["from_cache"] == 0


def test_cli_second_run_is_all_from_the_cache_and_no_cache_asks_again(tmp_path, capsys, monkeypatch):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    ultravox_library(tmp_path)

    def run(*extra):
        fetchers = ultravox_fetchers()
        monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: fetchers)
        assert main(["notes", str(tmp_path), "--json", *extra]) == 0
        return json.loads(capsys.readouterr().out), fetchers

    first, f1 = run()
    second, f2 = run()
    assert first["requests"] == 5 and second["requests"] == 0 and second["from_cache"] == 5
    assert f2.mb.urls == [] and f2.wiki.urls == []
    third, f3 = run("--no-cache")
    assert third["requests"] == 5 and third["from_cache"] == 0 and len(f3.mb.urls) == 3
    # the Preferences switch off means the same
    from core import notes_settings

    notes_settings.set_cache_enabled(False)
    fourth, _f4 = run()
    assert fourth["requests"] == 5 and fourth["from_cache"] == 0


# -- settings -------------------------------------------------------------------------------------------------------

