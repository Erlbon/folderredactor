"""The folder you CHOOSE gets its own note when it is eligible: choosing 'Ska' gives Ska/about.md (genre notes ticked), choosing an
artist folder gives artist.md, an album folder album.md. A generic place name (Music, Bands...) or an alphabetical grouping
gives the clear message, not 'no artist or album folders found'. Real engine, counted requests and tag reads, real dialog."""

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music import tags as scan_service  # noqa: E402
from core.music.flow import Fetchers, NotesEngine, build_proposals, scan, write_proposal  # noqa: E402
from core.music.local import LIBRARY_ROOT_MESSAGE  # noqa: E402
from tests.music_helpers import make_mp3, ultravox_fetchers, ultravox_library  # noqa: E402
from tests.test_music_genre_only import TagReads, genre_wiki, nothing_else, ska_tree  # noqa: E402


def targets_of(folder, kinds):
    return [(t.kind, t.folder.name) for t in scan([folder], kinds=kinds).targets]










def test_a_library_root_says_so_instead_of_the_cryptic_message(tmp_path, capsys, monkeypatch):
    from foldercli import cmd_notes
    from foldercli.main import main
    from redactor_common.cli import CliError

    pass  # the conftest isolates the settings
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: Fetchers(mb=nothing_else(), wiki=genre_wiki()))
    empty = tmp_path / "Empty"
    empty.mkdir()
    with pytest.raises(CliError) as why:
        main(["notes", str(empty), "--kind", "genre"])
    assert str(why.value) == LIBRARY_ROOT_MESSAGE and "no artist or album folders found" not in str(why.value)
    assert LIBRARY_ROOT_MESSAGE == ("This folder looks like a library root, not a genre: nothing to write here. "
                                    "Choose the genre folder itself or one level lower.")
    # the generic folder 'Music' holding artist folders, genre notes only: the same message (it is the root, not a genre)
    music = tmp_path / "Music"
    make_mp3(music / "Specials" / "First (1979)" / "01 a.mp3", "a", "Specials", "First", 1, "1979")
    with pytest.raises(CliError) as again:
        main(["notes", str(music), "--kind", "genre"])
    assert str(again.value) == LIBRARY_ROOT_MESSAGE
    # with a genre folder below it: that one is proposed, the root itself is not
    make_mp3(music / "Ska" / "Specials" / "First (1979)" / "01 a.mp3", "a", "Specials", "First", 1, "1979")
    assert main(["notes", str(music), "--kind", "genre", "--json", "--no-cache"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert [os.path.basename(r["folder"]) for r in document["results"] if r["status"] == "would-write"] == ["Ska"]
    assert [r["status"] for r in document["results"] if os.path.basename(r["folder"]) == "Music"] == ["skipped"]  # said, not written




