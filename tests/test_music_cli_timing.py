"""How long Create Notes takes, said plainly: the progress label's elapsed / remaining time, the 'Looked up N folders in
H:MM:SS' sentence (review banner, summary box, CLI), the scope dialog's time hint, a cancelled run that keeps what it did
and a second run that resumes from the cache, and the cache's per-request cost."""

import json
import os
import threading
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music.cache import ResponseCache  # noqa: E402
from core.music.flow import Fetchers  # noqa: E402
from core.music.local import KIND_ARTIST  # noqa: E402
from core.music.timing import (  # noqa: E402
    ALBUM_SECONDS, ARTIST_SECONDS, clock, estimate, format_duration, lookup_sentence, progress_suffix, scope_hint,
)
from tests.music_helpers import set_kinds  # noqa: E402,F401
from tests.music_helpers import FakeFetch, make_mp3, ultravox_fetchers, ultravox_library  # noqa: E402


# -- the words ----------------------------------------------------------------------------------------------------











# -- the progress label and the summary, on the real engine and the real review dialog ---------------------------

class FakeProgress:
    """The progress dialog's object (the worker talks only to this): it records what the user would read."""

    def __init__(self, cancel_after=None):
        self.labels, self.values, self.cancel_after = [], [], cancel_after

    def set_label(self, text):
        self.labels.append(text)

    def set_value(self, value):
        self.values.append(value)

    def should_cancel(self):
        return self.cancel_after is not None and len(self.labels) >= self.cancel_after


def install_fake_progress(monkeypatch, cancel_after=None, step=40.0):
    holder = {}

    def fake_run(parent, total, label, work, cancellable=False, title=""):
        progress = holder["progress"] = FakeProgress(cancel_after)
        work(progress)
        return None, progress.should_cancel()

    clock_state = {"now": 1000.0}

    def perf_counter():
        clock_state["now"] += step  # every look at the clock is `step` seconds later: 'slow' folders
        return clock_state["now"]

    monkeypatch.setattr(nd, "run_work_with_progress", fake_run)
    monkeypatch.setattr(nd, "time", SimpleNamespace(perf_counter=perf_counter))
    return holder


def six_artists(root):
    for i in range(6):
        make_mp3(root / f"Band {i}" / f"Album {i} (2000)" / "01 a.mp3", "a", f"Band {i}", f"Album {i}", 1, "2000")
    return root


def nothing_found():
    mb = FakeFetch([(r"ws/2/artist\?query", {"artists": []}), (r"ws/2/release-group\?query=", {"release-groups": []})])
    wiki = FakeFetch([(r"wikidata", {"entities": {}}), (r"search/title", {"pages": []}), (r"page/summary/", None)])
    return Fetchers(mb=mb, wiki=wiki)


def run_create(window, monkeypatch, root, cache, cancel_after=None):
    holder = install_fake_progress(monkeypatch, cancel_after)
    seen = {}
    fetchers = nothing_found()

    def trigger():
        nd.create_notes(window, [str(root)], True, lambda: fetchers, kinds=(KIND_ARTIST,), cache=cache)

    def scenario():
        yield from wait(lambda: review() is not None, "the review page")
        dlg = review()
        seen["banner"] = dlg.banner_label.text()
        seen["items"] = len(dlg.session.items)
        dlg._summary_box()
        seen["summary"] = dlg.last_summary
        dlg.done(0)

    drive(scenario, trigger)
    return holder["progress"], seen, fetchers






# -- the scope dialog's hint ---------------------------------------------------------------------------------------



# -- the command line ----------------------------------------------------------------------------------------------

def test_cli_reports_elapsed_requests_and_cache_hits_in_json_and_on_stderr(tmp_path, capsys, monkeypatch):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    fetchers = ultravox_fetchers()
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: fetchers)
    ultravox_library(tmp_path)
    code = main(["notes", str(tmp_path), "--json", "--no-cache"])
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert code == 0 and document["requests"] == 5 and document["from_cache"] == 0
    assert isinstance(document["elapsed_seconds"], float) and document["elapsed_seconds"] >= 0
    assert "Looked up 1 folder in 0:00:0" in captured.err and "(5 requests, 0 from the cache)" in captured.err


# -- the cache's cost per request ----------------------------------------------------------------------------------

