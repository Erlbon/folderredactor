"""The two things Pluteus reads from the notes to find artists and albums without a scan (2026-11-08, Pluteus b605eef):

  1. `layout:` in the front matter of a genre or collection folder's about.md: the levels below it down to the album
     ('letter/artist/album', 'country/artist/album', 'artist/album', 'album'); an about.md that is there gets the line added
     only on a yes, every other line kept;
  2. album.md in a box-set folder whose albums sit in disc folders (Box/Disc 1 - .../[1953] - Album/songs).

End to end on a real tree shaped like the owner's '780 - Music' (tiny real MP3s), the real scan, engine and writer; the
services are fakes that fail the test if they are asked anything unexpected."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import re  # noqa: E402
import urllib.parse  # noqa: E402

import pytest  # noqa: E402

from core.music.flow import Fetchers, NotesEngine, build_proposals, scan, write_proposal  # noqa: E402
from core.music.local import KIND_ALBUM, KIND_GENRE, album_files, album_folder_of, folder_layout  # noqa: E402
from core.note_amend import with_front_matter_line  # noqa: E402
from redactor_common.core.notes import STATE_CURRENT, note_status, parse_front_matter  # noqa: E402
from tests.music_helpers import FakeFetch, make_mp3  # noqa: E402

BOX = "Tom Lehrer - The remains of Tom Lehrer"


def owner_tree(root):
    """780 - Music/ with 0 - Bands/<letter>/<band>/<album>, 1.5 - Hip-hop/<country>/<artist>/<album>, 1.61 - Ska/<artist>/<album>,
    6.2 - Compilations/<album> (Various Artists) and Tom Lehrer's box set in disc folders."""
    music = root / "780 - Music"
    song = lambda path, artist, album, year, n=1, **kw: make_mp3(path / f"{n:02d} song {n}.mp3", f"song {n}", artist, album, n, year, **kw)  # noqa: E731
    song(music / "0 - Bands" / "H" / "Hellbillies" / "[1990] - Sylvsmeden", "Hellbillies", "Sylvsmeden", "1990")
    song(music / "0 - Bands" / "A-C" / "Ane Brun" / "[2003] - Spending Time with Morgan", "Ane Brun", "Spending Time with Morgan", "2003")
    lehrer = music / "0 - Bands" / "T" / "Tom Lehrer"
    song(lehrer / "[1965] - That Was the Year That Was", "Tom Lehrer", "That Was the Year That Was", "1965")
    song(lehrer / BOX / "Disc 1 - Songs by Tom Lehrer" / "[1953] - Songs by Tom Lehrer", "Tom Lehrer", "Songs by Tom Lehrer", "1953")
    song(lehrer / BOX / "Disc 1 - Songs by Tom Lehrer" / "[1953] - Songs by Tom Lehrer", "Tom Lehrer", "Songs by Tom Lehrer", "1953", 2)
    song(lehrer / BOX / "Disc 2 - More of Tom Lehrer" / "[1959] - More of Tom Lehrer", "Tom Lehrer", "More of Tom Lehrer", "1959")
    song(music / "1.5 - Hip-hop" / "Norway" / "Karpe" / "[2006] - Glasskår", "Karpe", "Glasskår", "2006")
    song(music / "1.5 - Hip-hop" / "USA" / "Nas" / "[1994] - Illmatic", "Nas", "Illmatic", "1994")
    song(music / "1.61 - Ska" / "The Specials" / "[1979] - Specials", "The Specials", "Specials", "1979")
    for title, year in (("Now That's What I Call Music", "1983"), ("Hits 90", "1990")):
        song(music / "6.2 - Compilations" / f"[{year}] - {title}", "Someone", title, year, albumartist="Various Artists")
    return music


def pluteus_layout_depth(value):
    """Pluteus's own rule (pluteus/subsonic.py layout_depth, b605eef), copied so the tests check what Pluteus will read."""
    levels = [w.strip().lower().rstrip("s") for w in value.split("/") if w.strip()]
    for word in ("artist", "album"):
        if word in levels:
            return levels.index(word) + 1
    return None


def genre_wiki():
    """Wikipedia: Hip-hop and Ska are music genres; nothing else is found (Norway, USA, Compilations)."""
    pages = {"Hip-hop": "Hip_hop_music", "Ska": "Ska"}

    def search(url):
        query = urllib.parse.unquote_plus(re.search(r"q=([^&]*)", url).group(1))
        for name, title in pages.items():
            if query.lower().startswith(name.lower()):
                return {"pages": [{"title": title.replace("_", " "), "description": "Music genre",
                                   "excerpt": f"{name} is a music genre"}]}
        return {"pages": []}

    def summary(url):
        title = urllib.parse.unquote(url.rsplit("/", 1)[1])
        return {"type": "standard", "title": title.replace("_", " "), "description": "Music genre",
                "extract": f"{title.replace('_', ' ')} is a music genre.",
                "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title}"}}}

    return FakeFetch([(r"search/title", search), (r"page/summary/(Hip_hop_music|Ska)$", summary), (r"page/summary/", None)])


def no_musicbrainz(request):
    raise AssertionError(f"MusicBrainz was asked about a genre folder: {request}")


# -- the layout line: which levels are below a folder -------------------------------------------------------------------

def test_each_kind_of_folder_says_its_layout_and_pluteus_finds_the_artists_at_that_depth(tmp_path):
    music = owner_tree(tmp_path)
    expected = {"0 - Bands": ("letter/artist/album", 2), "1.5 - Hip-hop": ("country/artist/album", 2),
                "1.61 - Ska": ("artist/album", 1), "6.2 - Compilations": ("album", 1)}
    for name, (layout, depth) in expected.items():
        assert folder_layout(music / name) == layout, name
        assert pluteus_layout_depth(layout) == depth
    assert folder_layout(music / "1.5 - Hip-hop" / "Norway") == "artist/album"
    assert folder_layout(music / "0 - Bands" / "T" / "Tom Lehrer" / BOX) == ""  # an album, no layout of its own


def test_the_scan_finds_every_folder_above_the_artists_and_the_box_as_one_album(tmp_path):
    music = owner_tree(tmp_path)
    found = scan([music], kinds=("artist", "album", "genre"))
    targets = {t.folder.name: t for t in found.targets}
    assert targets["0 - Bands"].kind == KIND_GENRE and targets["0 - Bands"].layout_only  # a generic name: a layout-only note
    for genre in ("1.5 - Hip-hop", "Norway", "USA", "1.61 - Ska", "6.2 - Compilations"):
        assert targets[genre].kind == KIND_GENRE and not targets[genre].layout_only, genre
    assert "780 - Music" not in targets  # the library root gets nothing
    assert {g.folder.name for g in found.groupings} == {"H", "A-C", "T"}  # letters still get no note
    assert targets[BOX].kind == KIND_ALBUM and targets["Tom Lehrer"].kind == "artist"
    assert not any(n.startswith("Disc ") or n.startswith("[1953]") or n.startswith("[1959]") for n in targets)
    box = music / "0 - Bands" / "T" / "Tom Lehrer" / BOX
    assert len(album_files(box)) == 3
    assert album_folder_of(box / "Disc 2 - More of Tom Lehrer" / "[1959] - More of Tom Lehrer" / "01 song 1.mp3") == box


def test_genre_and_collection_notes_are_written_with_the_layout_line(tmp_path):
    music = owner_tree(tmp_path)
    wiki = genre_wiki()
    engine = NotesEngine(Fetchers(mb=no_musicbrainz, wiki=wiki))
    targets = scan([music], kinds=("genre",)).targets
    proposals = {p.folder.name: p for p in build_proposals(targets, engine=engine)}
    for p in proposals.values():
        if p.writable:
            assert write_proposal(p).ok
    expected = {"0 - Bands": "letter/artist/album", "1.5 - Hip-hop": "country/artist/album", "1.61 - Ska": "artist/album",
                "6.2 - Compilations": "album"}
    for name, layout in expected.items():
        text = (music / name / "about.md").read_text(encoding="utf-8")
        meta, body = parse_front_matter(text)
        assert meta["layout"] == layout and meta["status"] == "draft", name
        assert note_status(music / name / "about.md").kind == STATE_CURRENT, name  # the stamp covers the layout line
    assert "is a music genre" in (music / "1.5 - Hip-hop" / "about.md").read_text(encoding="utf-8")
    bands = parse_front_matter((music / "0 - Bands" / "about.md").read_text(encoding="utf-8"))[1]
    assert "# Bands" in bands and "Sorted by first letter, one folder per artist." in bands
    assert "One folder per album." in (music / "6.2 - Compilations" / "about.md").read_text(encoding="utf-8")
    # Norway / USA: no genre article, so no note in a batch run (Hip-hop's about.md already says where their artists are)
    assert not (music / "1.5 - Hip-hop" / "Norway" / "about.md").exists()
    assert proposals["Norway"].layout == "artist/album" and not proposals["Norway"].writable
    # only notes, only where they belong: nothing at the root, in a letter folder or anywhere else
    written = sorted(p.relative_to(music).as_posix() for p in music.rglob("*") if p.is_file() and not p.name.endswith(".mp3"))
    assert written == ["0 - Bands/about.md", "1.5 - Hip-hop/about.md", "1.61 - Ska/about.md", "6.2 - Compilations/about.md"]


# -- an about.md that is already there: the line is added on a yes, nothing else changes ------------------------------------

OWN_NOTE = "---\ntitle: Ska\ntags: [two-tone, jamaica]\nstatus: draft\n---\n\n# Ska\n\nMy own words about ska.\n"


def test_an_existing_about_md_gets_only_the_layout_line_and_only_with_the_refresh_switch(tmp_path, recycle_bin):
    music = owner_tree(tmp_path)
    note = music / "1.61 - Ska" / "about.md"
    note.write_text(OWN_NOTE, encoding="utf-8", newline="\n")
    plain = scan([music], kinds=("genre",))
    assert "1.61 - Ska" not in {t.folder.name for t in plain.targets}  # without the switch: left alone, as before
    found = scan([music], kinds=("genre",), include_outdated=True)
    [target] = [t for t in found.targets if t.folder.name == "1.61 - Ska"]
    assert target.amend_layout == "artist/album" and target.update is not None
    engine = NotesEngine(Fetchers(mb=no_musicbrainz, wiki=FakeFetch([])))  # no lookup at all for this
    [proposal] = build_proposals([target], engine=engine)
    assert proposal.amend and proposal.is_update and proposal.writable and proposal.to_dict()["action"] == "add-layout"
    assert note.read_text(encoding="utf-8") == OWN_NOTE  # nothing written before the yes
    result = write_proposal(proposal)
    assert result.ok and len(recycle_bin.trashed) == 1  # the note as it was is in the Recycle Bin
    assert note.read_text(encoding="utf-8") == OWN_NOTE.replace("status: draft\n", "status: draft\nlayout: artist/album\n")
    again = scan([music], kinds=("genre",), include_outdated=True)
    assert "1.61 - Ska" not in {t.folder.name for t in again.targets}  # it has the line now


def test_a_note_of_ours_stays_ours_and_a_person_s_edit_meanwhile_is_never_overwritten(tmp_path, recycle_bin):
    music = owner_tree(tmp_path)
    engine = NotesEngine(Fetchers(mb=no_musicbrainz, wiki=genre_wiki()))
    [ska] = build_proposals([t for t in scan([music], kinds=("genre",)).targets if t.folder.name == "1.61 - Ska"], engine=engine)
    # a note of ours from before the layout line: the same note without it, stamped as it was then
    from core.music.render import render_genre_note

    old = render_genre_note(name="Ska", intro="Ska is a music genre.")
    note = music / "1.61 - Ska" / "about.md"
    note.write_text(old, encoding="utf-8", newline="\n")
    assert note_status(note).kind == STATE_CURRENT and ska.note_text
    [target] = [t for t in scan([music], kinds=("genre",), include_outdated=True).targets if t.folder.name == "1.61 - Ska"]
    [proposal] = build_proposals([target], engine=engine)
    assert write_proposal(proposal).ok
    assert note_status(note).kind == STATE_CURRENT  # the stamp was worked out again: still ours, untouched
    assert parse_front_matter(note.read_text(encoding="utf-8"))[0]["layout"] == "artist/album"
    # a person edits the note between the look and the yes: refused, their text kept
    note.write_text(OWN_NOTE, encoding="utf-8", newline="\n")
    [target] = [t for t in scan([music], kinds=("genre",), include_outdated=True).targets if t.folder.name == "1.61 - Ska"]
    [proposal] = build_proposals([target], engine=engine)
    note.write_text(OWN_NOTE + "\nOne more line.\n", encoding="utf-8", newline="\n")
    result = write_proposal(proposal)
    assert result.status == "changed" and "One more line." in note.read_text(encoding="utf-8")
    assert note_status(note).kind != STATE_CURRENT and "layout" not in parse_front_matter(note.read_text(encoding="utf-8"))[0]


@pytest.mark.parametrize("text,expected", [
    ("# Just text\n", "---\nlayout: album\n---\n\n# Just text\n"),                       # no front matter: a block is added
    ("---\ntitle: X\nstatus: reviewed\naudience: kids\n---\nBody\n",
     "---\ntitle: X\nstatus: reviewed\naudience: kids\nlayout: album\n---\nBody\n"),     # the person's keys stay
    ("---\nlayout: artist/album\n---\nBody\n", None),                                   # the person's own line stands
    ("---\nnot: [clean\n  oops\n---\nBody\n", None),                                    # a block that does not parse: left alone
])
def test_the_line_is_added_to_the_front_matter_and_nothing_else_moves(text, expected):
    assert with_front_matter_line(text, "layout", "album") == expected


# -- the box set: album.md, found two folders down ------------------------------------------------------------------------

LEHRER = "a3e1f0c4-1111-4222-8333-444455556666"
GROUPS = [("rg-songs", "Songs by Tom Lehrer", "1953", []), ("rg-more", "More of Tom Lehrer", "1959", []),
          ("rg-year", "That Was the Year That Was", "1965", ["Live"]), ("rg-remains", "The Remains of Tom Lehrer", "2000", ["Compilation"])]


def lehrer_musicbrainz():
    groups = [{"id": i, "title": t, "first-release-date": y, "primary-type": "Album", "secondary-types": s} for i, t, y, s in GROUPS]
    remains = {"id": "rel-remains", "title": "The Remains of Tom Lehrer", "status": "Official", "date": "2000-10-10", "country": "US",
               "artist-credit": [{"name": "Tom Lehrer", "joinphrase": ""}], "label-info": [{"label": {"name": "Rhino"}}],
               "media": [{"position": d, "format": "CD", "tracks": [
                   {"position": n, "number": str(n), "title": f"song {n}", "length": 2000,
                    "recording": {"id": f"rec-{d}-{n}", "title": f"song {n}", "length": 2000}} for n in (1, 2)]} for d in (1, 2)]}
    return FakeFetch([
        (r"ws/2/artist\?query", {"artists": [{"id": LEHRER, "name": "Tom Lehrer", "score": 100, "type": "Person", "country": "US",
                                              "sort-name": "Lehrer, Tom", "life-span": {"begin": "1928"}}]}),
        (r"ws/2/artist/[^?]+\?", {"id": LEHRER, "name": "Tom Lehrer", "type": "Person", "country": "US",
                                  "life-span": {"begin": "1928-04-09", "end": "2025-07-26", "ended": True}, "relations": []}),
        (r"ws/2/release-group\?artist=", {"release-groups": groups}),
        (r"ws/2/release-group\?query=", {"release-groups": []}),
        (r"ws/2/release-group/rg-remains", {"id": "rg-remains", "title": "The Remains of Tom Lehrer", "first-release-date": "2000",
                                            "primary-type": "Album", "secondary-types": ["Compilation"], "relations": []}),
        (r"ws/2/release\?release-group=rg-remains", {"releases": [{"id": "rel-remains", "title": "The Remains of Tom Lehrer",
                                                                  "status": "Official", "date": "2000-10-10", "country": "US",
                                                                  "media": [{"format": "CD", "track-count": 2}] * 2}]}),
        (r"ws/2/release/rel-remains", remains),
    ])


def no_wikipedia():
    return FakeFetch([(r"wikidata", {}), (r"search/title", {"pages": []}), (r"page/summary/", None)])


def test_the_box_set_gets_album_md_in_the_box_folder_and_nowhere_below(tmp_path):
    music = owner_tree(tmp_path)
    box = music / "0 - Bands" / "T" / "Tom Lehrer" / BOX
    [target] = [t for t in scan([box.parent], kinds=("album",)).targets if t.folder == box]
    engine = NotesEngine(Fetchers(mb=lehrer_musicbrainz(), wiki=no_wikipedia()))
    [proposal] = build_proposals([target], engine=engine)
    assert any("box set" in r for r in proposal.level_reasons), proposal.level_reasons
    assert proposal.local.box and proposal.local.title == "The remains of Tom Lehrer" and proposal.local.track_count == 3
    assert proposal.confidence.value == "confident", proposal.reasons
    assert write_proposal(proposal).ok
    meta, body = parse_front_matter((box / "album.md").read_text(encoding="utf-8"))
    assert meta["title"].casefold() == "the remains of tom lehrer" and meta["status"] == "draft" and "Tom Lehrer" in body
    notes = sorted(p.relative_to(box).as_posix() for p in box.rglob("*.md"))
    assert notes == ["album.md"]  # not in the disc folders, not in the albums inside them


def test_a_box_with_nothing_found_online_still_gets_its_album_md_from_the_tags_on_request(tmp_path):
    music = owner_tree(tmp_path)
    box = music / "0 - Bands" / "T" / "Tom Lehrer" / BOX
    [target] = [t for t in scan([box], kinds=("album",)).targets]
    mb = FakeFetch([(r"ws/2/artist\?query", {"artists": []}), (r"ws/2/release-group\?query=", {"release-groups": []})])
    engine = NotesEngine(Fetchers(mb=mb, wiki=no_wikipedia()))
    [proposal] = build_proposals([target], engine=engine)
    assert proposal.level == "album"  # never taken for loose tracks of an artist, whatever the album tags inside say
    local = engine.local_note(proposal)
    assert write_proposal(local).ok and (box / "album.md").exists()
    assert "song 1" in (box / "album.md").read_text(encoding="utf-8")


# -- the command line: --update --write adds the line ----------------------------------------------------------------------

def test_cli_update_adds_the_layout_line_to_existing_about_md_and_writes_the_missing_ones(tmp_path, monkeypatch, capsys, recycle_bin):
    import json

    from foldercli import cmd_notes
    from foldercli.main import main

    monkeypatch.setattr(cmd_notes, "make_music_fetchers", lambda use: Fetchers(mb=no_musicbrainz, wiki=genre_wiki()))
    music = owner_tree(tmp_path)
    (music / "1.61 - Ska" / "about.md").write_text(OWN_NOTE, encoding="utf-8", newline="\n")
    assert main(["notes", str(music), "--kind", "genre", "--json", "--no-cache"]) == 0  # a look: nothing written
    document = json.loads(capsys.readouterr().out)
    assert "layout" not in parse_front_matter((music / "1.61 - Ska" / "about.md").read_text(encoding="utf-8"))[0]
    assert not (music / "0 - Bands" / "about.md").exists()
    assert main(["notes", str(music), "--kind", "genre", "--update", "--write", "--json", "--no-cache"]) == 0
    document = json.loads(capsys.readouterr().out)
    status = {os.path.basename(r["folder"]): r.get("status") for r in document["results"]}
    assert status["1.61 - Ska"] == "updated" and status["0 - Bands"] == "written", status
    ska = (music / "1.61 - Ska" / "about.md").read_text(encoding="utf-8")
    assert ska == OWN_NOTE.replace("status: draft\n", "status: draft\nlayout: artist/album\n")
    for name, layout in (("0 - Bands", "letter/artist/album"), ("1.5 - Hip-hop", "country/artist/album"), ("6.2 - Compilations", "album")):
        assert parse_front_matter((music / name / "about.md").read_text(encoding="utf-8"))[0]["layout"] == layout
