"""What carries over from mp3redactor's notes (core/music/render.py): the note format, so its notes count as current.
The note text itself is tested through the engine (test_music_flow.py, test_music_discography.py ...)."""

from core.music.render import CURRENT_NOTE_FORMAT


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
