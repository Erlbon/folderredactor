"""A genre / collection folder can cover SEVERAL genres ('1.61 - Ska' = ska and ska punk): the note merges the Wikipedia
introductions, one section per genre and one credit; a name is split only when every part verifies as a genre of its own;
the review page edits the genres and rebuilds the row in place; the command line has --genres."""

import json
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from core.music.flow import Fetchers, NotesEngine, build_proposals, scan, split_genre_name  # noqa: E402
from core.music.render import wikipedia_credits  # noqa: E402
from redactor_common.core.notes import parse_front_matter  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3, set_kinds  # noqa: E402
from tests.test_music_genre_only import nothing_else  # noqa: E402

SKA = ("Ska is a music genre that originated in Jamaica in the late 1950s and was the precursor to rocksteady and reggae. "
       "It combined elements of Caribbean mento with American jazz and rhythm and blues.")
SKA_PUNK = ("Ska punk is a fusion genre that mixes ska with punk rock. It is closely tied to third wave ska, which reached its "
            "zenith in the mid-1990s.")


def page(title, extract, description="Music genre"):
    wiki_title = title.replace(" ", "_")
    return {"type": "standard", "title": title, "description": description, "extract": extract,
            "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{wiki_title}"}}}


def hit(title, blurb):
    return {"pages": [{"title": title, "description": "Music genre", "excerpt": blurb}]}


def genre_wiki():
    return FakeFetch([
        (r"(?i)search/title\?q=Ska\+punk\+music", hit("Ska punk", "Ska punk is a fusion genre")),
        (r"(?i)search/title\?q=Ska\+music", hit("Ska", "Ska is a music genre")),
        (r"(?i)search/title\?q=Rock\+and\+Roll\+music", hit("Rock and roll", "Rock and roll is a genre of popular music")),
        (r"(?i)search/title\?q=Rock\+music", hit("Rock music", "Rock is a broad genre of popular music")),
        (r"(?i)search/title\?q=Drum\+and\+Bass\+music", hit("Drum and bass", "Drum and bass is a genre of electronic music")),
        (r"search/title", {"pages": []}),
        (r"page/summary/Ska_punk$", page("Ska punk", SKA_PUNK)),
        (r"page/summary/Ska$", page("Ska", SKA)),
        (r"page/summary/Rock_and_roll$", page("Rock and roll", "Rock and roll is a genre of popular music that originated in the US.")),
        (r"page/summary/Rock_music$", page("Rock music", "Rock is a broad genre of popular music.")),
        (r"page/summary/Drum_and_bass$", page("Drum and bass", "Drum and bass is a genre of electronic music.")),
        (r"page/summary/", None),
    ])


def genre_folder(root, name):
    make_mp3(root / name / "Some Artist" / "Album (2000)" / "01 a.mp3", "a", "Some Artist", "Album", 1, "2000")
    return root / name


def proposal_for(root, name, engine_setup=None):
    wiki = genre_wiki()
    engine = NotesEngine(Fetchers(mb=nothing_else(), wiki=wiki))
    if engine_setup:
        engine_setup(engine)
    found = scan([root], kinds=("genre",))
    [proposal] = build_proposals([t for t in found.targets if t.folder.name == name], engine=engine)
    return proposal, wiki, engine


def without_stamp(text):
    return "".join(line for line in text.splitlines(keepends=True) if not re.match(r"(generator|note-format|body-sha):", line))


EXPECTED = f"""---
title: Ska
genres: [ska, ska punk]
links: [https://en.wikipedia.org/wiki/Ska, https://en.wikipedia.org/wiki/Ska_punk]
status: draft
---

# Ska

## Ska

{SKA}

## Ska punk

{SKA_PUNK}

---
*Draft. Introductions from Wikipedia ([Ska](https://en.wikipedia.org/wiki/Ska), [Ska punk](https://en.wikipedia.org/wiki/Ska_punk)), CC BY-SA 4.0.*
"""


# -- the split ----------------------------------------------------------------------------------------------------





# -- the engine ---------------------------------------------------------------------------------------------------















# -- the review page ----------------------------------------------------------------------------------------------



# -- the command line ---------------------------------------------------------------------------------------------------

def test_cli_genres_writes_the_merged_note_and_checks_its_argument(tmp_path, monkeypatch, capsys):
    from foldercli import cmd_notes
    from foldercli.main import main
    from redactor_common.cli import CliError

    pass  # the conftest isolates the settings
    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: Fetchers(mb=nothing_else(), wiki=genre_wiki()))
    music = tmp_path / "780 - Music"
    genre_folder(music, "1.61 - Ska")
    code = main(["notes", str(music), "--kind", "genre", "--write", "--no-cache", "--genres", "1.61 - Ska=Ska,Ska punk"])
    assert code == 0
    written = (music / "1.61 - Ska" / "about.md").read_text(encoding="utf-8")
    assert without_stamp(written) == EXPECTED
    with pytest.raises(CliError):
        main(["notes", str(music), "--kind", "genre", "--genres", "no equals sign"])
