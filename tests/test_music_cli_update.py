"""Updating notes made by an older version, only when asked: every note we write is stamped (generator, note-format,
body-sha); the scan lists 'outdated-untouched' and 'legacy' notes as UPDATE proposals only with include_outdated;
'edited', 'foreign' and 'current' notes are never listed or touched; an update goes through replace_note (the old
note to the Recycle Bin); the review page shows Before / after and never pre-ticks an update; the CLI's --update."""

import json
import os

import pytest

from core.music.flow import (
    Confidence, Fetchers, NotesEngine, build_proposals, scan, summarize, write_proposal,
)
from core.music.local import KIND_ALBUM, KIND_ARTIST
from core.music.render import CURRENT_NOTE_FORMAT
from core.music.review import ReviewSession, note_diff
from redactor_common.core.note_text import credit_footer
from redactor_common.core.notes import (
    STATE_CURRENT, STATE_EDITED, STATE_FOREIGN, STATE_LEGACY, STATE_OUTDATED, NoteFrontMatter, note_status,
    parse_front_matter, render_note,
)
from tests.music_helpers import make_mp3, ultravox_fetchers, ultravox_library

GEN = "mp3redactor 2026-10-01#01"


def our_note(title, fmt=CURRENT_NOTE_FORMAT, text="Old text."):
    return render_note(NoteFrontMatter(title=title, generator=GEN, note_format=fmt), f"# {title}\n\n{text}")


def legacy_note(title, text="Old text."):
    return render_note(NoteFrontMatter(title=title), f"# {title}\n\n{text}\n\n" + credit_footer(["Facts from MusicBrainz"]))


def put(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def five_states(root):
    """Five artist folders, each with one album folder and an artist.md in one of the five states."""
    notes = {
        "Cur": our_note("Cur"),
        "Old": our_note("Old", fmt=1),
        "Edit": our_note("Edit").replace("Old text.", "My own words."),
        "Leg": legacy_note("Leg"),
        "Foreign": "---\ntitle: Foreign\n---\n\nWritten by hand.\n",
    }
    for name, text in notes.items():
        make_mp3(root / name / f"{name} Album (2000)" / "01 a.mp3", "a", name, f"{name} Album", 1, "2000")
        put(root / name / "artist.md", text)
    return root


def names(found, attr="targets"):
    return sorted(t.folder.name for t in getattr(found, attr))


# -- the stamp ---------------------------------------------------------------------------------------------------



# -- the scan ----------------------------------------------------------------------------------------------------









# -- the engine and the writing ---------------------------------------------------------------------------------

def ultravox_with_old_notes(tmp_path, artist_note, album_note):
    artist = ultravox_library(tmp_path)
    put(artist / "artist.md", artist_note)
    put(artist / "Vienna (1980)" / "album.md", album_note)
    return artist








# -- the review session ------------------------------------------------------------------------------------------



# -- the command line --------------------------------------------------------------------------------------------

@pytest.fixture
def cli(monkeypatch, capsys, tmp_path):
    from foldercli import cmd_notes
    from foldercli.main import main

    pass  # the conftest isolates the settings
    state = {"fetchers": ultravox_fetchers()}
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: state["fetchers"])

    def run(*argv):
        state["fetchers"] = ultravox_fetchers()
        code = main(["notes", *argv, "--json", "--no-cache"])
        return code, json.loads(capsys.readouterr().out)

    return run


def old_ultravox(tmp_path, artist_note=None):
    artist = ultravox_library(tmp_path)
    put(artist / "artist.md", artist_note or our_note("Ultravox", fmt=1))
    return artist


def rows(document):
    return {(r["kind"], r["folder"].replace("\\", "/").split("/")[-1]): r for r in document["results"]}


def test_cli_without_update_leaves_every_existing_note_alone(tmp_path, cli):
    artist = old_ultravox(tmp_path)
    before = (artist / "artist.md").read_text(encoding="utf-8")
    code, document = cli(str(tmp_path), "--kind", "artist", "--write")
    assert code == 0 and (artist / "artist.md").read_text(encoding="utf-8") == before
    assert rows(document)[("artist", "Ultravox")]["status"] == "has-note"


def test_cli_update_reports_and_with_write_replaces_only_outdated_untouched_notes(tmp_path, cli, recycle_bin):
    artist = old_ultravox(tmp_path)
    code, document = cli(str(tmp_path), "--kind", "artist", "--update")
    row = rows(document)[("artist", "Ultravox")]
    assert code == 0 and row["status"] == "would-update" and row["action"] == "update"
    assert "Old text." in (artist / "artist.md").read_text(encoding="utf-8")  # a report: nothing changed
    assert document["updates"] == 1 and document["left_alone"] == 0
    code, document = cli(str(tmp_path), "--kind", "artist", "--update", "--write")
    assert rows(document)[("artist", "Ultravox")]["status"] == "updated"
    assert "Ultravox were a British new wave band" in (artist / "artist.md").read_text(encoding="utf-8")
    assert note_status(str(artist / "artist.md"), CURRENT_NOTE_FORMAT).kind == STATE_CURRENT
    assert len(recycle_bin.trashed) == 1
    # a second run: it is current now, nothing to update
    code, again = cli(str(tmp_path), "--kind", "artist", "--update", "--write")
    assert again["updates"] == 0 and again["already_current"] == 1 and len(recycle_bin.trashed) == 1


def test_cli_legacy_notes_need_the_extra_flag(tmp_path, cli, recycle_bin):
    artist = old_ultravox(tmp_path, legacy_note("Ultravox"))
    code, document = cli(str(tmp_path), "--kind", "artist", "--update")
    assert rows(document)[("artist", "Ultravox")]["old_state"] == STATE_LEGACY
    code, document = cli(str(tmp_path), "--kind", "artist", "--update", "--write")
    row = rows(document)[("artist", "Ultravox")]
    assert row["status"] == "legacy" and "--update-legacy" in row["message"]
    assert "Old text." in (artist / "artist.md").read_text(encoding="utf-8") and recycle_bin.trashed == []
    code, document = cli(str(tmp_path), "--kind", "artist", "--update-legacy", "--write")
    assert rows(document)[("artist", "Ultravox")]["status"] == "updated" and len(recycle_bin.trashed) == 1
    assert note_status(str(artist / "artist.md"), CURRENT_NOTE_FORMAT).kind == STATE_CURRENT


def test_cli_never_touches_an_edited_or_a_foreign_note_even_with_every_flag(tmp_path, cli, recycle_bin):
    edited = our_note("Ultravox", fmt=1).replace("Old text.", "My own words.")
    artist = old_ultravox(tmp_path, edited)
    code, document = cli(str(tmp_path), "--kind", "artist", "--update", "--update-legacy", "--write")
    assert (artist / "artist.md").read_text(encoding="utf-8") == edited and recycle_bin.trashed == []
    assert document["left_alone"] == 1 and rows(document)[("artist", "Ultravox")]["status"] == "left-alone"
    foreign = "---\ntitle: Mine\n---\n\nmine\n"
    put(artist / "artist.md", foreign)
    code, document = cli(str(tmp_path), "--kind", "artist", "--update", "--update-legacy", "--write")
    assert (artist / "artist.md").read_text(encoding="utf-8") == foreign and document["left_alone"] == 1


def test_cli_update_records_the_replacement_in_the_opt_in_history(tmp_path, cli, journal):
    from core import history

    old_ultravox(tmp_path)
    cli(str(tmp_path), "--kind", "artist", "--update", "--write")
    assert journal.entries() == []  # history is off: nothing recorded
    old_ultravox(tmp_path)
    put(tmp_path / "Ultravox" / "artist.md", our_note("Ultravox", fmt=1))
    history.set_history_enabled(True)
    cli(str(tmp_path), "--kind", "artist", "--update", "--write")
    [entry] = journal.entries()
    assert entry.kind == "note-update" and "Recycle Bin" in str(entry.changes)  # batch 4: a refresh has its own kind
    import os

    assert os.path.isfile(os.path.join(history.notes_backup_base(), "notes_backup", f"{entry.id}.md"))  # the older text, for the undo
