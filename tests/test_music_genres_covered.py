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
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402

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

def test_the_split_is_only_a_candidate():
    assert split_genre_name("Ska & Ska Punk") == ["Ska", "Ska Punk"]
    assert split_genre_name("Ska and Ska Punk") == ["Ska", "Ska Punk"]
    assert split_genre_name("Ska, Ska punk / Reggae + Dub") == ["Ska", "Ska punk", "Reggae", "Dub"]
    assert split_genre_name("Ska") == ["Ska"] and split_genre_name("Rock and Roll") == ["Rock", "Roll"]  # (then not verified)
    assert split_genre_name("") == [""]


def test_the_credit_for_several_pages_is_one_sentence():
    assert wikipedia_credits([("Ska", "https://en.wikipedia.org/wiki/Ska"), ("Ska punk", "https://en.wikipedia.org/wiki/Ska_punk")]) == (
        "Introductions from Wikipedia ([Ska](https://en.wikipedia.org/wiki/Ska), [Ska punk](https://en.wikipedia.org/wiki/Ska_punk)), "
        "CC BY-SA 4.0")
    assert wikipedia_credits([("Ska", "https://en.wikipedia.org/wiki/Ska")]).startswith("Introduction from Wikipedia ([Ska]")


# -- the engine ---------------------------------------------------------------------------------------------------















# -- the review page ----------------------------------------------------------------------------------------------



# -- the command line ---------------------------------------------------------------------------------------------------

