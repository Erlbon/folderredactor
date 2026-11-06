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

def test_put_get_and_ttl(cache):
    cache.put("k", b'{"a": 1}')
    assert cache.get("k") == (200, b'{"a": 1}')
    assert cache.get("missing") is None
    cache.clock.now += TTL_SECONDS - 10
    assert cache.get("k") is not None  # 30 days minus a bit: still fresh
    cache.clock.now += 20
    assert cache.get("k") is None  # expired and removed
    assert cache.count() == 0


def test_not_found_and_empty_results_live_one_day_errors_never(cache):
    cache.put("gone", b"", 404)
    cache.put("empty", b'{"artists": [], "count": 0}')
    cache.put("busy", b"busy", 503)
    cache.put("odd", b"x", 500)
    assert cache.count() == 2  # the 503 and the 500 were never stored
    assert looks_empty(b'{"pages": []}') and not looks_empty(b'{"pages": [1]}') and not looks_empty(b"not json")
    cache.clock.now += NEGATIVE_TTL_SECONDS + 1
    assert cache.get("gone") is None and cache.get("empty") is None
    cache.put("full", b'{"artists": [1]}')
    cache.clock.now += NEGATIVE_TTL_SECONDS + 1
    assert cache.get("full") is not None


def test_eviction_drops_the_least_recently_used_and_keeps_under_the_cap(tmp_path):
    clock = Clock()
    c = ResponseCache(tmp_path / "small.sqlite", max_bytes=2000, clock=clock)
    c.used_refresh = 0  # every read refreshes the entry, so the test can show what a read does to the eviction order
    for i in range(10):
        clock.now += 1
        c.put(f"key{i}", b'"' + b"x" * 298 + b'"')
        clock.now += 0.5
        if i >= 1:
            assert c.get("key0") is not None  # key0 is used all the time: it survives the eviction
    assert c.total_bytes() <= 2000
    assert c.get("key0") is not None and c.get("key9") is not None and c.get("key1") is None
    c.close()


def test_a_broken_cache_file_is_dropped_silently_and_started_again(tmp_path):
    path = tmp_path / "broken.sqlite"
    path.write_bytes(b"this is not a database at all" * 50)
    c = ResponseCache(path)
    assert c.get("k") is None  # no exception
    c.put("k", b'"v"')
    assert c.get("k") == (200, b'"v"')
    c.close()
    # corrupted later, while the object lives on: the next call recovers too
    c2 = ResponseCache(tmp_path / "later.sqlite")
    c2.put("a", b"1")
    c2.close()
    (tmp_path / "later.sqlite").write_bytes(b"\x00" * 4096)
    c3 = ResponseCache(tmp_path / "later.sqlite")
    assert c3.get("a") is None
    c3.put("b", b"2")
    assert c3.get("b") == (200, b"2")
    c3.close()


def test_an_unusable_location_means_no_cache_never_an_error(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    c = ResponseCache(blocker / "inside" / "cache.sqlite")  # a folder cannot be made below a file
    c.put("k", b'"v"')
    assert c.get("k") is None and c.count() == 0


def test_the_cache_is_thread_safe(cache):
    errors = []

    def worker(n):
        try:
            for i in range(60):
                cache.put(f"t{n}-{i}", f'"value {n} {i}"'.encode())
                assert cache.get(f"t{n}-{i}") == (200, f'"value {n} {i}"'.encode())
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert errors == [] and cache.count() == 8 * 60 and cache.hits == 8 * 60


def test_clear_empties_it(cache):
    cache.put("a", b"1")
    cache.put("b", b"2")
    assert cache.clear() == 2 and cache.count() == 0


# -- the wrappers -------------------------------------------------------------------------------------------------

def test_cached_fetch_asks_the_network_once_per_url_and_the_disk_serves_the_next_run(cache):
    inner = FakeFetch([(r"example\.org/a", {"x": 1}), (r"example\.org/gone", None)])
    stats = RequestStats()
    fetch = CachedFetch(inner, "mb", cache, stats)
    assert fetch("https://example.org/a") == fetch("https://example.org/a")
    with pytest.raises(urllib.error.HTTPError):
        fetch("https://example.org/gone")
    with pytest.raises(urllib.error.HTTPError) as again:
        fetch("https://example.org/gone")
    assert again.value.code == 404
    assert len(inner.urls) == 2 and stats.requests == 2 and stats.from_memory == 2
    # a second run (a new wrapper = a new engine) is answered from the disk, the network is not touched
    inner2 = FakeFetch([])
    stats2 = RequestStats()
    fetch2 = CachedFetch(inner2, "mb", cache, stats2)
    assert json.loads(fetch2("https://example.org/a")) == {"x": 1}
    with pytest.raises(urllib.error.HTTPError):
        fetch2("https://example.org/gone")
    assert inner2.urls == [] and stats2.requests == 0 and stats2.from_cache == 2


def test_errors_are_never_remembered_and_the_next_call_tries_again(cache):
    calls = []

    def flaky(request):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.HTTPError("https://example.org/x", 503, "busy", {}, None)
        return b'{"ok": true}'

    fetch = CachedFetch(flaky, "mb", cache)
    with pytest.raises(urllib.error.HTTPError):
        fetch("https://example.org/x")
    assert fetch("https://example.org/x") == b'{"ok": true}' and len(calls) == 2
    assert cache.count() == 1


def test_the_key_is_the_url_never_a_header(cache):
    request = urllib.request.Request("https://example.org/q", headers={"Authorization": "Discogs token=SECRET-TOKEN"})
    fetch = CachedFetch(lambda r: b'{"a": 1}', "wiki", cache)
    fetch(request)
    cache.close()
    raw = open(cache.path, "rb").read()
    assert b"SECRET-TOKEN" not in raw and b"Authorization" not in raw


def test_cached_discogs_never_stores_the_token_and_serves_the_second_run_from_disk(cache):
    fake = FakeFetch([(r"database/search", {"results": [{"id": 1, "title": "A - B"}]})])
    client = DiscogsClient("SECRET-TOKEN-123", fetch=fake, throttle=Throttle(0))
    stats = RequestStats()
    wrapped = CachedDiscogs(client, cache, stats)
    first = wrapped.get_json("database/search", type="release", q="a b")
    assert wrapped.get_json("database/search", type="release", q="a b") == first
    assert len(fake.urls) == 1 and stats.from_memory == 1
    fake2 = FakeFetch([])
    wrapped2 = CachedDiscogs(DiscogsClient("SECRET-TOKEN-123", fetch=fake2, throttle=Throttle(0)), cache, RequestStats())
    assert wrapped2.get_json("database/search", type="release", q="a b") == first and fake2.urls == []
    cache.close()
    assert b"SECRET-TOKEN-123" not in open(cache.path, "rb").read()


# -- the engine's request counts --------------------------------------------------------------------------------

def mb_urls(fetchers):
    return fetchers.mb.urls


def patterns(urls, *regexes):
    return {rx: sum(1 for u in urls if re.search(rx, u)) for rx in regexes}


def test_artist_only_issues_no_album_requests_at_all(tmp_path):
    ultravox_library(tmp_path)
    fetchers = ultravox_fetchers()
    targets = scan([tmp_path], kinds=(KIND_ARTIST,)).targets
    assert [t.kind for t in targets] == ["artist"]
    proposals = build_proposals(targets, fetchers)
    assert proposals[0].confidence == Confidence.CONFIDENT  # the local albums still verified the artist
    urls = fetchers.mb.urls + fetchers.wiki.urls
    assert len(fetchers.mb.urls) == 3 and len(fetchers.wiki.urls) == 2  # the artist's own requests, nothing else
    assert not [u for u in urls if re.search(r"release-group/rg-|ws/2/release/|release\?release-group|release-group\?query|\(album\)", u)]


def test_album_requests_per_album_and_no_duplicates(tmp_path):
    ultravox_library(tmp_path)
    fetchers = ultravox_fetchers()
    build_proposals(scan([tmp_path], kinds=(KIND_ARTIST, KIND_ALBUM)).targets, fetchers)
    urls = fetchers.mb.urls + fetchers.wiki.urls
    assert len(urls) == len(set(urls)), "a URL was asked twice in one run"
    assert len(fetchers.mb.urls) == 8 and len(fetchers.wiki.urls) == 7  # was 10 + 7: no repeated release fetch, one discography browse per artist


def test_the_release_list_request_is_dropped_when_the_release_group_lookup_carries_the_releases(tmp_path):
    ultravox_library(tmp_path)
    fetchers = ultravox_fetchers()
    detail = dict(RECORDED["mb_rg_vienna_album"])
    detail["releases"] = [{"id": "rel-vienna-uk", "title": "Vienna", "date": "1980-07-11", "country": "GB",
                           "status": "Official", "media": [{"track-count": 9}]}]
    fetchers.mb.routes.insert(0, (r"ws/2/release-group/[^?]+\?inc=url-rels%2Bgenres%2Btags%2Bannotation%2Breleases%2Bmedia",
                                  detail))
    targets = scan([tmp_path], kinds=(KIND_ALBUM,)).targets
    [vienna] = [t for t in targets if t.folder.name == "Vienna (1980)"]
    [proposal] = build_proposals([vienna], fetchers)
    assert proposal.confidence == Confidence.CONFIDENT and "1. " in proposal.note_text
    assert patterns(fetchers.mb.urls, r"release\?release-group") == {r"release\?release-group": 0}


def test_a_second_run_is_answered_entirely_from_the_disk_cache(tmp_path, cache):
    ultravox_library(tmp_path)
    targets = scan([tmp_path], kinds=(KIND_ARTIST, KIND_ALBUM)).targets
    first = ultravox_fetchers()
    engine1 = NotesEngine(first, cache=cache)
    notes1 = [p.note_text for p in build_proposals(targets, engine=engine1)]
    n_first = len(first.mb.urls) + len(first.wiki.urls)
    assert engine1.stats.requests == n_first == 15 and engine1.stats.from_cache == 0
    second = ultravox_fetchers()
    engine2 = NotesEngine(second, cache=cache)  # a new engine: no memory of the first run, only the disk
    notes2 = [p.note_text for p in build_proposals(targets, engine=engine2)]
    assert second.mb.urls == [] and second.wiki.urls == []
    assert engine2.stats.requests == 0 and engine2.stats.from_cache == 15 and notes2 == notes1
    assert "0 request(s), 15 from the cache" in engine2.stats.summary()


def test_a_cancelled_run_resumes_from_the_cache(tmp_path, cache):
    ultravox_library(tmp_path)
    targets = scan([tmp_path], kinds=(KIND_ARTIST, KIND_ALBUM)).targets
    first = ultravox_fetchers()
    build_proposals(targets, engine=NotesEngine(first, cache=cache), cancel=lambda: False)
    # only the first folder was done when the run was cancelled
    cache.clear()
    part = ultravox_fetchers()
    engine = NotesEngine(part, cache=cache)
    build_proposals(targets[:1], engine=engine)
    done = len(part.mb.urls) + len(part.wiki.urls)
    rest = ultravox_fetchers()
    engine2 = NotesEngine(rest, cache=cache)
    build_proposals(targets, engine=engine2)
    assert engine2.stats.from_cache == done and len(rest.mb.urls) + len(rest.wiki.urls) == 15 - done


def test_two_engines_without_a_disk_cache_do_not_share_the_memo(tmp_path):
    ultravox_library(tmp_path)
    targets = scan([tmp_path], kinds=(KIND_ARTIST,)).targets
    a, b = ultravox_fetchers(), ultravox_fetchers()
    build_proposals(targets, engine=NotesEngine(a))
    build_proposals(targets, engine=NotesEngine(b))
    assert len(a.mb.urls) == len(b.mb.urls) == 3  # nothing leaks from one run to the next


# -- settings (the command line's cache tests come with the music `notes` command, plan step 10) -------------------

def test_settings_remember_the_kinds_choice_and_the_cache_switch():
    from core import notes_settings, settings
    from core.music import settings as music_settings

    assert music_settings.kinds() == ("artist",) and notes_settings.cache_enabled() is True
    music_settings.set_kinds("both")
    notes_settings.set_cache_enabled(False)
    assert music_settings.kinds() == ("artist", "album") and notes_settings.cache_enabled() is False
    assert settings.get_setting("notes.music", "kinds", "") == "artist,album"
    settings.set_setting("notes.music", "kinds", "nonsense")
    assert music_settings.kinds() == ("artist",)


def test_music_and_video_share_one_lookup_cache_file():
    from core import notes_settings
    from core.music import cache

    assert cache.cache_path() == notes_settings.cache_path()
