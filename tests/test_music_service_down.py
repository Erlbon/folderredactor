"""One service that cannot be reached must not block the rest (Erlend, 2026-11-13: MusicBrainz was down and the window
answered 'skipped' for every folder, also for a pasted Wikipedia link). The run's early stop is for ONE run; a link is
asked for whatever the run did; a Wikipedia link gives its thin draft without MusicBrainz."""

import os
import urllib.error

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.music.flow import Confidence, Fetchers, NotesEngine, build_proposals, scan  # noqa: E402
from tests.music_helpers import make_mp3, ultravox_fetchers, ultravox_library  # noqa: E402
from tests.test_music_hard_band import DACHNIKI, band_library, wiki_fetch  # noqa: E402

WIKI_LINK = "https://en.wikipedia.org/wiki/Leningrad_(band)"


class Switch:
    """A fetch that can be taken down and brought back."""

    def __init__(self, inner=None):
        self.inner, self.down, self.calls = inner, inner is None, 0

    def __call__(self, request):
        self.calls += 1
        if self.down:
            raise urllib.error.URLError("no network")
        return self.inner(request)


def test_the_early_stop_ends_with_the_run_the_next_look_up_asks_again(tmp_path):
    ultravox_library(tmp_path)
    fetchers = ultravox_fetchers()
    mb = fetchers.mb = Switch(fetchers.mb)
    mb.down = True
    engine = NotesEngine(fetchers)
    targets = list(scan([tmp_path]).targets)
    first = build_proposals(targets, engine=engine)
    assert "skipped" in first[2].reasons[0]
    mb.down = False  # MusicBrainz is back: the engine the window keeps must ask again
    second = build_proposals(targets, engine=engine)
    assert not any("skipped" in " ".join(p.reasons) for p in second)
    assert any(p.confidence == Confidence.CONFIDENT for p in second)


def test_a_wikipedia_link_gives_its_thin_draft_while_musicbrainz_is_down(tmp_path):
    band_library(tmp_path)
    engine = NotesEngine(Fetchers(mb=Switch(), wiki=wiki_fetch()))
    target = next(t for t in scan([tmp_path], kinds=("artist",)).targets)
    [proposal] = build_proposals([target], engine=engine)
    assert proposal.confidence == Confidence.NONE
    built = engine.rebuild(proposal, link=WIKI_LINK)
    assert built.confidence == Confidence.CONFIDENT and built.writable and built.sources == ["wikipedia"]
    assert "Russian ska punk band" in built.note_text
    assert any("MusicBrainz could not be reached" in r for r in built.reasons), built.reasons


def test_a_wikipedia_link_for_an_album_works_while_musicbrainz_is_down(tmp_path):
    band_library(tmp_path)
    engine = NotesEngine(Fetchers(mb=Switch(), wiki=wiki_fetch()))
    target = next(t for t in scan([tmp_path], kinds=("album",)).targets)
    [proposal] = build_proposals([target], engine=engine)
    assert proposal.confidence == Confidence.NONE and any("Could not reach MusicBrainz" in p for p in proposal.problems)
    built = engine.rebuild(proposal, link=WIKI_LINK)
    assert built.confidence == Confidence.CONFIDENT and built.sources == ["wikipedia"]


def test_a_folder_with_a_link_is_asked_for_after_the_run_stopped_early(tmp_path):
    for name in ("Aaa", "Bbb"):
        make_mp3(tmp_path / name / "One (2000)" / "01 a.mp3", "a", name, "One", 1, "2000")
    make_mp3(tmp_path / "Leningrad" / f"{DACHNIKI} (2000)" / "01 a.mp3", "a", "Leningrad", DACHNIKI, 1, "2000")
    engine = NotesEngine(Fetchers(mb=Switch(), wiki=wiki_fetch()))
    engine.set_links("Leningrad", WIKI_LINK)
    targets = sorted(scan([tmp_path], kinds=("artist",)).targets, key=lambda t: t.folder.name)
    proposals = build_proposals(targets, engine=engine)
    assert [p.folder.name for p in proposals] == ["Aaa", "Bbb", "Leningrad"]
    assert proposals[2].confidence == Confidence.CONFIDENT and proposals[2].sources == ["wikipedia"]
