"""Book notes (core/booknotes, plan step 17; Erlend's D27-D31, 2026-11-21): names from folders, the books' own OPF, the
local ISFDB database, Open Library and Wikipedia, and the notes they make. Every tree and database is built in tmp_path;
the network is FakeFetch."""

import os
import sqlite3
import zipfile
from pathlib import Path

import pytest

from core.booknotes import local, render
from core.booknotes.flow import Fetchers, NotesEngine, scan
from core.booknotes.isfdb import IsfdbBooks, database_problem
from core.shelf_scan import Target, literal
from redactor_common.core.notes_model import Confidence
from tests.video_helpers import FakeFetch

OPF = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
 <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
  <dc:title>{title}</dc:title>
  <dc:creator opf:role="aut">Iain M. Banks</dc:creator>
  <dc:date>{year}-01-01</dc:date>
  <meta name="calibre:series" content="Culture"/>
  <meta name="calibre:series_index" content="{number}"/>
 </metadata>
</package>"""
CONTAINER = """<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
 <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def epub(path: Path, title: str, year: str = "1987", number: str = "1.0") -> Path:
    """Also under folder names that end in a dot ('Banks, Iain M.'): Windows drops that dot unless the path is literal."""
    os.makedirs(literal(path.parent), exist_ok=True)
    with zipfile.ZipFile(literal(path), "w") as book:
        book.writestr("mimetype", "application/epub+zip")
        book.writestr("META-INF/container.xml", CONTAINER)
        book.writestr("OEBPS/content.opf", OPF.format(title=title, year=year, number=number))
    return path


def make_dir(folder: Path) -> Path:
    os.makedirs(literal(folder), exist_ok=True)
    return folder


def put(path: Path, data: bytes) -> Path:
    make_dir(path.parent)
    with open(literal(path), "wb") as handle:
        handle.write(data)
    return path


def isfdb_file(tmp_path: Path) -> str:
    """A small ISFDB database in epubredactor's schema: works + works_fts."""
    path = tmp_path / "isfdb.db"
    con = sqlite3.connect(path)
    con.execute("create table works (id integer primary key, title text, authors_text text, year integer, series text, "
                "series_num text, series_parent text, language text, ttype text, variant_of integer)")
    con.execute("create table editions (id integer primary key, work_id integer)")
    con.execute("create virtual table works_fts using fts5(title, authors_text)")
    rows = [
        (1, "Consider Phlebas", "Iain M. Banks", 1987, "Culture", "1", "", "en", "NOVEL", None),
        (2, "The Player of Games", "Iain M. Banks", 1988, "Culture", "2", "", "en", "NOVEL", None),
        (3, "Against a Dark Background", "Iain M. Banks", 1993, "", "", "", "en", "NOVEL", None),
        (4, "Use of Weapons", "Iain M. Banks", 1990, "Culture", "3", "", "en", "NOVEL", None),
        (5, "Bedenke Phlebas", "Iain M. Banks", 1990, "Culture", "1", "", "de", "NOVEL", 1),  # a translation: left out
        (6, "The Wasp Factory", "Iain Banks", 1984, "", "", "", "en", "NOVEL", None),  # another ISFDB name
        (7, "A Story", "Iain M. Banks", 1991, "", "", "", "en", "SHORTFICTION", None),  # not a book
    ]
    con.executemany("insert into works values (?,?,?,?,?,?,?,?,?,?)", rows)
    con.executemany("insert into works_fts (rowid, title, authors_text) values (?,?,?)", [(r[0], r[1], r[2]) for r in rows])
    con.commit()
    con.close()
    return str(path)


WIKI_BANKS = {"title": "Iain Banks", "extract": "Iain Menzies Banks was a Scottish writer of science fiction.",
              "description": "Scottish writer", "type": "standard",
              "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Iain_Banks"}}}


def wiki_routes(extra=()):
    return list(extra) + [
        (r"wikidata\.org.*Q312579", {"entities": {"Q312579": {"sitelinks": {"enwiki": {"title": "Iain Banks"}}}}}),
        (r"page/summary/Iain_Banks", WIKI_BANKS),
        (r"page/summary/Fantasy_fiction", None),
        (r"page/summary/Fantasy_literature", {"title": "Fantasy literature", "type": "standard",
                                              "extract": "Fantasy literature is literature set in an imaginary universe.",
                                              "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Fantasy_literature"}}}),
        (r"search/title", {"pages": []}),
    ]


OL_SEARCH_BANKS = {"docs": [{"key": "OL123A", "name": "Iain M. Banks", "birth_date": "16 February 1954",
                             "death_date": "9 June 2013", "work_count": 60, "top_work": "Consider Phlebas"}]}
OL_AUTHOR_BANKS = {"name": "Iain M. Banks", "birth_date": "16 February 1954", "death_date": "9 June 2013",
                   "remote_ids": {"wikidata": "Q312579"}}


def ol_routes():
    return [
        (r"search/authors\.json", OL_SEARCH_BANKS),
        (r"authors/OL123A\.json", OL_AUTHOR_BANKS),
        (r"search\.json\?author=OL123A", {"docs": [{"title": "Consider Phlebas", "first_publish_year": 1987},
                                                   {"title": "Excession", "first_publish_year": 1996},
                                                   {"title": "consider phlebas", "first_publish_year": 1988}]}),
    ]


def engine(isfdb: str = "", ol=None, wiki=None, wikipedia=True) -> NotesEngine:
    return NotesEngine(Fetchers(openlibrary=ol or FakeFetch(ol_routes()), wiki=wiki or FakeFetch(wiki_routes()),
                                wikipedia=wikipedia, isfdb=isfdb))


# -- names and local books --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("folder, name", [
    ("Banks, Iain M.", "Iain M. Banks"), ("Le Guin, Ursula K. (1929-2018)", "Ursula K. Le Guin"),
    ("Terry Pratchett", "Terry Pratchett"),
])
def test_author_name_from_the_folder(folder, name):
    assert local.author_name(folder) == name


@pytest.mark.parametrize("folder, title", [
    ("02 - Culture (10 books)", "Culture"), ("Discworld", "Discworld"), ("1. The Expanse [2011-2021]", "The Expanse"),
])
def test_series_title_from_the_folder(folder, title):
    assert local.series_title(folder) == title


def test_the_books_own_opf_gives_title_series_and_number(tmp_path):
    folder = tmp_path / "Banks, Iain M." / "Culture"
    epub(folder / "Iain M. Banks - The Player of Games.epub", "The Player of Games", "1988", "2.0")
    put(folder / "Iain M. Banks - Excession.pdf", b"%PDF")
    books = local.read_books(folder)
    assert [(b.title, b.series, b.number, b.year) for b in books] == [
        ("Excession", "", "", ""), ("The Player of Games", "Culture", "2", "1988")]


def test_a_broken_epub_falls_back_to_the_file_name(tmp_path):
    folder = tmp_path / "Banks, Iain M."
    make_dir(folder)
    put(folder / "Iain M. Banks - Matter.epub", b"not a zip")
    assert local.read_books(folder)[0].title == "Matter"


# -- ISFDB ------------------------------------------------------------------------------------------------------------

def test_isfdb_gives_the_authors_own_books_only(tmp_path):
    books = IsfdbBooks(isfdb_file(tmp_path))
    titles = [w.title for w in books.author_works("Iain M. Banks")]
    assert titles == ["Consider Phlebas", "The Player of Games", "Use of Weapons", "Against a Dark Background"]


def test_isfdb_series_in_series_order(tmp_path):
    works = IsfdbBooks(isfdb_file(tmp_path)).series_works("culture", "Iain M. Banks")
    assert [(w.number, w.title) for w in works] == [("1", "Consider Phlebas"), ("2", "The Player of Games"),
                                                    ("3", "Use of Weapons")]


def test_a_missing_or_wrong_isfdb_file_is_said_plainly(tmp_path):
    assert "not found" in database_problem(str(tmp_path / "none.db"))
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("create table x (a)").connection.close()
    assert "doesn't look like" in database_problem(str(other))


# -- the notes --------------------------------------------------------------------------------------------------------

def test_author_note_from_isfdb_with_series_first_and_the_wikipedia_introduction(tmp_path):
    folder = tmp_path / "Fiction" / "Banks, Iain M."
    epub(folder / "Consider Phlebas.epub", "Consider Phlebas")
    p = engine(isfdb_file(tmp_path)).build_proposal(Target(folder, "author"))
    assert p.confidence == Confidence.CONFIDENT
    text = p.note_text
    assert "title: Iain M. Banks" in text and "years: 1954-2013" in text and "status: draft" in text
    assert "Scottish writer of science fiction" in text
    culture, other = text.index("### Culture"), text.index("### Other books")
    assert culture < text.index("- Consider Phlebas (1987)") < text.index("- The Player of Games (1988)") < \
        text.index("- Use of Weapons (1990)") < other < text.index("- Against a Dark Background (1993)")
    assert "Bedenke" not in text and "Wasp Factory" not in text and "A Story" not in text
    assert "ISFDB" in text and "[[" not in text


def test_author_note_from_open_library_when_isfdb_does_not_know_them(tmp_path):
    folder = tmp_path / "Banks, Iain M."
    make_dir(folder)
    p = engine("").build_proposal(Target(folder, "author"))
    assert p.confidence == Confidence.CONFIDENT and p.ol_key == "OL123A"
    assert "## Books" in p.note_text and "- Consider Phlebas (1987)" in p.note_text and "- Excession (1996)" in p.note_text
    assert p.note_text.count("onsider Phlebas (19") == 1  # one line per title
    assert "###" not in p.note_text  # Open Library knows no series: one flat list
    assert "Open Library" in p.note_text


def test_two_open_library_authors_of_one_name_are_told_apart_by_the_books_in_the_folder(tmp_path):
    folder = tmp_path / "Smith, John"
    epub(folder / "Blue Water.epub", "Blue Water")
    ol = FakeFetch([
        (r"search/authors\.json", {"docs": [{"key": "OL1A", "name": "John Smith", "work_count": 9},
                                            {"key": "OL2A", "name": "John Smith", "work_count": 4}]}),
        (r"search\.json\?author=OL1A", {"docs": [{"title": "Red Sand"}]}),
        (r"search\.json\?author=OL2A", {"docs": [{"title": "Blue Water", "first_publish_year": 2001}]}),
        (r"authors/OL2A\.json", {"name": "John Smith"}),
    ])
    p = engine("", ol=ol).build_proposal(Target(folder, "author"))
    assert p.confidence == Confidence.CONFIDENT and p.ol_key == "OL2A"


def test_two_authors_of_one_name_and_nothing_to_tell_them_apart_is_uncertain(tmp_path):
    folder = tmp_path / "Smith, John"
    make_dir(folder)
    ol = FakeFetch([
        (r"search/authors\.json", {"docs": [{"key": "OL1A", "name": "John Smith"}, {"key": "OL2A", "name": "John Smith"}]}),
        (r"search\.json\?author=", {"docs": []}),
    ])
    p = engine("", ol=ol).build_proposal(Target(folder, "author"))
    assert p.confidence == Confidence.UNCERTAIN and not p.note_text
    assert {c.id for c in p.candidates} == {"OL1A", "OL2A"}


def test_series_note_in_isfdb_reading_order(tmp_path):
    folder = tmp_path / "Banks, Iain M." / "Culture"
    make_dir(folder)
    p = engine(isfdb_file(tmp_path), wikipedia=False).build_proposal(Target(folder, "series"))
    assert p.confidence == Confidence.CONFIDENT
    assert "- 1. Consider Phlebas (1987)\n- 2. The Player of Games (1988)\n- 3. Use of Weapons (1990)" in p.note_text
    assert "**Author:** Iain M. Banks" in p.note_text


def test_series_without_isfdb_uses_the_books_numbers_and_asks_for_a_check(tmp_path):
    folder = tmp_path / "Banks, Iain M." / "Culture"
    epub(folder / "b.epub", "The Player of Games", "1988", "2")
    epub(folder / "a.epub", "Consider Phlebas", "1987", "1")
    p = engine("", wikipedia=False).build_proposal(Target(folder, "series"))
    assert p.confidence == Confidence.UNCERTAIN
    assert "- 1. Consider Phlebas (1987)\n- 2. The Player of Games (1988)" in p.note_text


def test_genre_note_is_the_wikipedia_paragraph(tmp_path):
    folder = tmp_path / "813 - Fantasy"
    make_dir(folder)
    p = engine("").build_proposal(Target(folder, "genre"))
    assert p.confidence == Confidence.CONFIDENT
    assert "title: Fantasy" in p.note_text and "imaginary universe" in p.note_text


def test_genre_without_an_article_gets_no_note(tmp_path):
    folder = tmp_path / "Grimdark Sea Shanties"
    make_dir(folder)
    p = engine("", wiki=FakeFetch([(r".", None)])).build_proposal(Target(folder, "genre"))
    assert p.confidence == Confidence.NONE and not p.note_text


def test_a_broken_isfdb_setting_falls_back_to_open_library_and_says_so(tmp_path):
    folder = tmp_path / "Banks, Iain M."
    make_dir(folder)
    p = engine(str(tmp_path / "missing.db")).build_proposal(Target(folder, "author"))
    assert p.confidence == Confidence.CONFIDENT
    assert any("ISFDB" in problem for problem in p.problems)


def test_look_up_on_one_folder_keeps_only_that_folder(tmp_path):
    genre = tmp_path / "Fantasy"
    epub(genre / "Banks, Iain M." / "a.epub", "Consider Phlebas")
    epub(genre / "Le Guin, Ursula K." / "b.epub", "A Wizard of Earthsea")
    author = genre / "Banks, Iain M."
    assert [t.folder.name for t in scan([author], include_subfolders=False).targets] == ["Banks, Iain M."]
    assert {t.folder.name for t in scan([genre], include_subfolders=True).targets} == {
        "Fantasy", "Banks, Iain M.", "Le Guin, Ursula K."}


def test_minimal_note_from_the_folder_name(tmp_path):
    folder = tmp_path / "Banks, Iain M."
    make_dir(folder)
    e = engine("")
    p = e.local_note(e.build_proposal(Target(folder, "author")))
    assert "# Iain M. Banks" in p.note_text and render.LOCAL_ONLY_CREDIT in p.note_text
