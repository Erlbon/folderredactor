"""Create Notes, 2026-10-15: 'Look up by link' also works for a genre / collection folder (the link is the genre's Wikipedia
article), and choosing a level builds at once, like a pasted link does (there was a second 'Build' press; only 'Skip' keeps a
button, because a skipped row leaves the list). Real review dialog (offscreen), the real engine for the link."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from core.music.flow import Confidence, Fetchers, NotesEngine, Proposal, build_proposals, scan  # noqa: E402
from core.music.link import LinkError  # noqa: E402
from core.music.local import Target  # noqa: E402
from core.music.review import ReviewSession  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402


SKA_PUNK = {"type": "standard", "title": "Ska punk", "description": "Music genre",
            "extract": "Ska punk is a fusion genre that combines ska and punk rock.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Ska_punk"}}}


def genre_proposal():
    target = Target(Path("C:/lib/Genres/1.61 - Ska"), "genre", "Genres")
    return Proposal(target, Confidence.UNCERTAIN, level="genre", suggested_levels=["genre-collection", "skip"],
                    reasons=["no Wikipedia page about a music genre called 'Ska' could be verified"])


def dialog(proposals, rebuild):
    dlg = NotesReviewDialog(ReviewSession(proposals), "list", rebuild, lambda p, c: True)
    dlg.show()
    dlg.resize(1100, 700)
    settle()
    click_row(dlg, 0)
    return dlg


# -- the engine: a Wikipedia link names the genre ------------------------------------------------------------------

def tree_with_a_genre(root):
    for artist in ("Specials", "Madness"):
        make_mp3(root / "Genres" / "Ska" / artist / "First (1979)" / "01 a.mp3", "a", artist, "First", 1, "1979")
    return root / "Genres"


def test_a_wikipedia_link_builds_the_genre_note_from_that_article(tmp_path):
    genres = tree_with_a_genre(tmp_path)
    wiki = FakeFetch([(r"search/title", {"pages": []}), (r"page/summary/Ska_punk$", SKA_PUNK), (r"page/summary/", None)])
    engine = NotesEngine(Fetchers(mb=lambda r: (_ for _ in ()).throw(AssertionError("no MusicBrainz for a genre")), wiki=wiki))
    [proposal] = build_proposals(scan([genres], kinds=("genre",)).targets, engine=engine)
    assert proposal.note_kind == "about" and proposal.confidence != Confidence.CONFIDENT      # nothing found by name
    built = engine.rebuild(proposal, link="https://en.wikipedia.org/wiki/Ska_punk")
    assert built.confidence == Confidence.CONFIDENT and built.note_kind == "about" and "fusion genre" in built.note_text
    assert built.genres == ["Ska punk"] and "wikipedia" in built.sources
    assert any(r.startswith("chosen by you from a link") for r in built.reasons), built.reasons
    assert "https://en.wikipedia.org/wiki/Ska_punk" in built.note_text


@pytest.mark.parametrize("link,words", [
    ("https://musicbrainz.org/artist/2bf704b3-1111-4222-8333-444455556666", "Wikipedia article about the genre"),
    ("https://en.wikipedia.org/wiki/No_such_page", "No Wikipedia article"),
])
def test_a_link_that_cannot_name_a_genre_is_refused_in_plain_words(tmp_path, link, words):
    genres = tree_with_a_genre(tmp_path)
    wiki = FakeFetch([(r"search/title", {"pages": []}), (r"page/summary/", None)])
    engine = NotesEngine(Fetchers(mb=lambda r: None, wiki=wiki))
    [proposal] = build_proposals(scan([genres], kinds=("genre",)).targets, engine=engine)
    with pytest.raises(LinkError, match=words):
        engine.rebuild(proposal, link=link)


# -- the review page -------------------------------------------------------------------------------------------------



