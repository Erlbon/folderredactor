"""How long Create Notes takes, said plainly: the progress label's elapsed / remaining time, the 'Looked up N folders in
H:MM:SS' sentence (review banner, summary box, CLI), the scope dialog's time hint, a cancelled run that keeps what it did
and a second run that resumes from the cache, and the cache's per-request cost."""

import os
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music.cache import ResponseCache  # noqa: E402
from core.music.timing import (  # noqa: E402
    ALBUM_SECONDS, ARTIST_SECONDS, clock, estimate, format_duration, lookup_sentence, progress_suffix, scope_hint,
)


# -- the words ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("seconds,text", [(0, "0 s"), (35, "35 s"), (59.4, "59 s"), (60, "1 min"), (240, "4 min"),
                                          (3599, "1 h"), (3600, "1 h"), (6060, "1 h 41 min"), (7200, "2 h")])
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


def test_clock_and_the_lookup_sentence():
    assert clock(0) == "0:00:00" and clock(6612) == "1:50:12" and clock(75) == "0:01:15"
    assert lookup_sentence(656, 6612, 5120, 800) == "Looked up 656 folders in 1:50:12 (5120 requests, 800 from the cache)."
    assert lookup_sentence(1, 3, 1, 0) == "Looked up 1 folder in 0:00:03 (1 request, 0 from the cache)."


def test_the_progress_suffix_says_nothing_silly_early_on():
    assert progress_suffix(0, 656, 2, []) == "" and progress_suffix(2, 656, 20, [10, 10]) == ""
    assert progress_suffix(656, 656, 6000, [10] * 20) == ""  # nothing left
    assert progress_suffix(3, 656, 30, [10, 10, 10]) == ", 30 s elapsed, about 1 h 49 min left"
    assert progress_suffix(12, 656, 240, [20] * 12) == ", 4 min elapsed, about 3 h 35 min left"  # 644 left at 20 s each


def test_the_estimate_follows_the_recent_folders_and_counts_cache_hits_as_fast():
    slow = progress_suffix(20, 100, 200, [10.0] * 20)
    resumed = progress_suffix(20, 100, 200, [10.0] * 8 + [0.05] * 12)  # the latest dozen came from the cache
    assert "about 13 min left" in slow and resumed.endswith("almost done")  # 80 folders at 0.05 s each
    assert progress_suffix(90, 100, 900, [9.0] * 12).endswith("about 90 s left".replace("90 s", "2 min"))  # 10 left at 9 s


def test_the_scope_hint_is_for_big_scopes_with_album_notes_only():
    assert scope_hint(40, 50, 0, "both") == "" and scope_hint(300, 350, 5, "artist") == ""  # small / the fast choice
    text = scope_hint(250, 400, 3, "both")
    assert text.startswith("About 650 folders: roughly ") and "with album notes" in text
    assert "artist notes only is about 2x faster" in text
    assert format_duration(estimate(250, 400, 3, "both")) in text
    assert estimate(1, 1, 0, "both") == pytest.approx(ARTIST_SECONDS + ALBUM_SECONDS)
    assert scope_hint(120, 0, 0, "both") == ""  # only artists: 'both' is not slower, nothing to say about albums
    assert "Everything" not in scope_hint(250, 400, 3, "all") and "About 653 folders" in scope_hint(250, 400, 3, "all")


# -- the cache's cost per request ----------------------------------------------------------------------------------

def test_the_cache_costs_next_to_nothing_per_request_and_holds_up_under_threads(tmp_path):
    cache = ResponseCache(tmp_path / "speed.sqlite")
    body = b'{"x": "' + b"a" * 4000 + b'"}'
    start = time.perf_counter()
    for i in range(600):
        cache.put(f"k{i}", body)
    put_ms = (time.perf_counter() - start) / 600 * 1000
    start = time.perf_counter()
    for i in range(600):
        assert cache.get(f"k{i}") == (200, body)
    hit_ms = (time.perf_counter() - start) / 600 * 1000
    # a MusicBrainz request costs 1100 ms: even a loose bound is a tiny share of it (measured: about 0.3 and 0.01 ms)
    assert put_ms < 25 and hit_ms < 25, (put_ms, hit_ms)
    errors = []

    def worker(n):
        try:
            for i in range(200):
                assert cache.get(f"k{(i * 7 + n) % 600}") is not None
                cache.put(f"t{n}-{i}", body)
        except Exception as exc:  # noqa: BLE001
            errors.append(repr(exc))

    start = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    per_call = (time.perf_counter() - start) / (8 * 400) * 1000
    assert errors == [] and per_call < 25, per_call
    cache.close()
