"""The parts of the music note text that need no engine (core/music/render.py). mp3redactor's engine tests
(tests/test_notes_flow.py) come with the engine, plan step 8."""

from pathlib import Path

from core.music.local import LocalTrack
from core.music.render import CURRENT_NOTE_FORMAT, TrackInfo, compare_tracks


def test_comparison_pairs_equal_titles_even_when_numbers_and_durations_differ():
    tracks = [TrackInfo(1, 1, "Sleepwalk", 193), TrackInfo(1, 5, "Astradyne", 428)]
    local = [LocalTrack(path=Path("01 Astradyne.mp3"), title="Astradyne", track=1, seconds=12.0),
             LocalTrack(path=Path("99 Bonus.flac"), title="Bonus", track=99, seconds=60.0)]
    result = compare_tracks(local, tracks)
    assert [(t.title, f.name) for t, f in result.present] == [("Astradyne", "01 Astradyne.mp3")]
    assert [t.title for t in result.missing] == ["Sleepwalk"] and [f.name for f in result.extra] == ["99 Bonus.flac"]


def test_a_current_note_written_by_mp3redactor_counts_as_current_here(tmp_path):
    """The notes mp3redactor wrote before the move have the same shape (note-format 2): this app leaves them alone instead
    of offering to 'refresh' them because another program's name is in the generator line."""
    from core.music.local import scan
    from redactor_common.core.notes import NoteFrontMatter, render_note
    from tests.music_helpers import ultravox_library

    artist = ultravox_library(tmp_path)
    old = render_note(NoteFrontMatter(title="Ultravox", generator="mp3redactor 2026-10-30#01",
                                      note_format=CURRENT_NOTE_FORMAT), "# Ultravox\n\nWritten by mp3redactor.")
    (artist / "artist.md").write_bytes(old.encode("utf-8"))
    found = scan([tmp_path], kinds=["artist"], include_outdated=True)
    assert found.targets == [] and found.skipped[0].state == "current"
