"""The one engine core every media type shares (core/notes_engine.py): music and video write, record and undo through the
same functions, the run loop is one, Wikipedia is asked at one pace, and a History failure never breaks a write."""

import pytest

from core import history, notes_engine
from tests.music_helpers import ultravox_fetchers, ultravox_library
from tests.video_helpers import fake_fetchers, make_series


def test_music_and_video_use_the_one_core():
    from core.music import flow as music
    from core.video import flow as video

    for name in ("write_proposal", "record_note_created", "undo_note_entry", "summarize"):
        assert getattr(music, name) is getattr(notes_engine, name) is getattr(video, name), name
    assert music._WIKI_FETCH is notes_engine.wiki_fetch()
    assert video.NotesEngine(video.Fetchers(key="k"))._wiki.inner is notes_engine.wiki_fetch()


def test_the_run_loop_reports_progress_cancels_and_hands_each_proposal_over():
    class Engine:
        def build_proposal(self, target):
            return f"proposal of {target.folder.name}"

    class Target:
        def __init__(self, name):
            self.kind, self.folder = "artist", type("F", (), {"name": name})()

    seen, labels = [], []
    built = notes_engine.build_proposals([Target("A"), Target("B")], Engine(), progress=lambda d, t, label: labels.append(label),
                                         on_proposal=seen.append)
    assert built == seen == ["proposal of A", "proposal of B"] and labels == ["artist: A", "artist: B", ""]
    assert notes_engine.build_proposals([Target("A")], Engine(), cancel=lambda: True) == []


@pytest.mark.parametrize("media", ["music", "video"])
def test_a_history_failure_never_breaks_the_write(tmp_path, monkeypatch, media):
    """The note is written; History could not record it: logged, never raised (the video code of step 5 raised here)."""
    if media == "music":
        from core.music.flow import build_proposals, scan

        ultravox_library(tmp_path)
        [proposal] = build_proposals(scan([tmp_path], kinds=["artist"]).targets, ultravox_fetchers())
    else:
        from core.video.flow import build_proposals, scan

        make_series(tmp_path)
        [proposal] = build_proposals(scan([tmp_path]).targets, fake_fetchers())
    history.set_history_enabled(True)

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(notes_engine, "record_note_entry", broken)
    result = notes_engine.write_proposal(proposal)
    assert result.ok and proposal.path and open(proposal.path, encoding="utf-8").read().startswith("---")


def test_a_written_note_is_recorded_and_undone_through_the_core(tmp_path, recycle_bin):
    from core.music.flow import build_proposals, scan

    history.set_history_enabled(True)
    ultravox_library(tmp_path)
    [proposal] = build_proposals(scan([tmp_path], kinds=["artist"]).targets, ultravox_fetchers())
    assert notes_engine.write_proposal(proposal).ok
    [entry] = history.get_journal().entries()
    assert notes_engine.undo_note_entry(entry) == "" and recycle_bin.trashed == [proposal.path]
