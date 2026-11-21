"""Which folders of a BOOKS and a COMICS library get a note (core/books.py, core/comics.py), for Notes > Scan for Notes
(2026-11-21): folder structure and names only, no file opened. Also the four-way media guess and Scan in the window on a
comics tree."""

import os
from pathlib import Path

import pytest

from core import books, comics
from core.shelf_scan import literal
from core.media_guess import BOOKS, COMICS, MUSIC, guess_kind, guess_media
from tests.notes_gui_helpers import open_library, pump, select


@pytest.fixture
def lib(tmp_path):
    folder = tmp_path / "Library"
    folder.mkdir()
    return folder


def touch(path: Path, text: str = "x") -> Path:
    """Also under folder names that end in a dot ('Banks, Iain M.'), as the real trees have them."""
    os.makedirs(literal(path.parent), exist_ok=True)
    with open(literal(path), "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def found(result) -> dict[str, str]:
    """{folder name: kind} of every folder judged, left or not."""
    return {t.folder.name: t.kind for t in result.targets} | {s.folder.name: s.kind for s in result.skipped}


def left(result) -> set[str]:
    return {t.folder.name for t in result.targets}


# -- comics -----------------------------------------------------------------------------------------------------------

def comics_tree(lib: Path) -> Path:
    root = lib / "741.59 - Comic Books"
    marvel = root / "5973 - US" / "M" / "3 - Marvel (1961-2012)"
    touch(marvel / "Spider-Man (1963-)" / "Amazing 001.cbz")
    touch(marvel / "Spider-Man (1963-)" / "Annuals" / "Annual 01.cbz")  # inside a series: belongs to it
    touch(marvel / "_Crossovers" / "Secret Wars (1984-1985)" / "Secret Wars 01.cbz")
    touch(marvel / "_Crossovers" / "about.md", "# Crossovers\n")
    touch(root / "5973 - US" / "_" / "Odd One (1990)" / "Odd 01.cbz")  # '_' marks a folder for attention: no note
    touch(root / "594 - EU" / "5943 - German" / "Fix und Foxi (1953-1994)" / "series.md", "# Fix und Foxi\n")
    touch(root / "594 - EU" / "5943 - German" / "Fix und Foxi (1953-1994)" / "Heft 001.cbr")
    (root / "594 - EU" / "Empty").mkdir()
    return root


def test_comics_series_folders_hold_comics_and_the_folders_above_get_about(lib):
    root = comics_tree(lib)
    result = comics.scan([root])
    assert found(result) == {
        "Spider-Man (1963-)": "series", "Secret Wars (1984-1985)": "series", "Odd One (1990)": "series",
        "Fix und Foxi (1953-1994)": "series",
        "3 - Marvel (1961-2012)": "grouping", "_Crossovers": "grouping", "5973 - US": "grouping", "594 - EU": "grouping",
        "5943 - German": "grouping",
    }  # not the root ('Comic Books' is a place), not the letter 'M', not '_', not 'Empty', not 'Annuals'
    assert left(result) == set(found(result)) - {"_Crossovers", "Fix und Foxi (1953-1994)"}


def test_loose_comics_in_a_country_and_a_publisher_leave_them_groupings(lib):
    """'594 - EU/59481 - Norwegian' on the share: loose albums next to underscore publishers, and '_Egmont' with loose Kid
    Paddle albums next to its 'Nemi' series. Before 2026-11-21 the whole country was one series."""
    norway = lib / "741.59 - Comic Books" / "594 - EU" / "59481 - Norwegian"
    touch(norway / "Hauk 006 (Se-Bladene, 1957).cbz")
    touch(norway / "_Egmont" / "Kid Paddle 001 - Spillegalskap (Egmont Serieforlaget, 2001-).cbz")
    touch(norway / "_Egmont" / "Nemi" / "Nemi 115 (Hjemmet, 2013-).cbz")
    touch(norway / "_Semic" / "Fantomet (1950-)" / "Fantomet 001.cbz")
    touch(norway / "_Hjemmet" / "Donald Duck & Co (1948-)" / "DDC 001.cbz")
    touch(norway / "Downs Duck (Ronny Haugeland)" / "downsbuss.jpg")  # pictures only: no comics, no note
    result = comics.scan([lib / "741.59 - Comic Books"])
    assert found(result) == {
        "594 - EU": "grouping", "59481 - Norwegian": "grouping", "_Egmont": "grouping", "_Semic": "grouping",
        "_Hjemmet": "grouping", "Nemi": "series", "Fantomet (1950-)": "series", "Donald Duck & Co (1948-)": "series"}


def test_a_series_with_an_annuals_folder_stays_one_series(lib):
    series = lib / "Spider-Man (1963-)"
    touch(series / "Amazing 001.cbz")
    touch(series / "Annuals" / "Annual 01.cbz")
    touch(series / "Extras" / "Extra 01.cbz")
    assert found(comics.scan([series])) == {"Spider-Man (1963-)": "series"}


def test_a_comics_folder_chosen_below_the_root_is_judged_itself(lib):
    marvel = comics_tree(lib) / "5973 - US" / "M" / "3 - Marvel (1961-2012)"
    assert "3 - Marvel (1961-2012)" in left(comics.scan([marvel]))


# -- books ------------------------------------------------------------------------------------------------------------

def books_tree(lib: Path) -> Path:
    root = lib / "eLib"
    space = root / "Science Fiction" / "Space Opera"
    touch(space / "Banks, Iain M." / "Consider Phlebas.epub")
    touch(space / "Banks, Iain M." / "author.md", "# Banks\n")
    touch(space / "Hamilton, Peter F." / "Night's Dawn" / "The Reality Dysfunction.epub")  # author > series
    touch(space / "Hamilton, Peter F." / "Night's Dawn" / "Extras" / "Map.pdf")  # below a series: no note
    touch(root / "Science Fiction" / "Plato" / "Republic.pdf")  # books directly, no comma: the author
    calibre = root / "Fantasy" / "Le Guin, Ursula K." / "A Wizard of Earthsea (12)"
    touch(calibre / "A Wizard of Earthsea.epub")
    touch(calibre / "metadata.opf")
    touch(root / "Fantasy" / "Tolkien" / "The Hobbit (7)" / "The Hobbit.epub")  # Calibre layout, no comma
    touch(root / "Fantasy" / "Tolkien" / "The Hobbit (7)" / "metadata.opf")
    touch(root / "Fantasy" / "A" / "Abercrombie, Joe" / "The Blade Itself.mobi")  # letter bucket: no note
    touch(root / "Fantasy" / "_" / "Unsorted, Someone" / "Book.azw3")
    touch(root / "813 - Fiction, American" / "Twain, Mark" / "Huckleberry Finn.epub")  # a numbered genre, not an author
    (root / "Poetry").mkdir()
    return root


def test_books_authors_series_and_genres(lib):
    result = books.scan([books_tree(lib)])
    assert found(result) == {
        "Banks, Iain M.": "author", "Hamilton, Peter F.": "author", "Night's Dawn": "series", "Plato": "author",
        "Le Guin, Ursula K.": "author", "Tolkien": "author", "Abercrombie, Joe": "author", "Unsorted, Someone": "author",
        "Twain, Mark": "author",
        "Science Fiction": "genre", "Space Opera": "genre", "Fantasy": "genre", "813 - Fiction, American": "genre",
    }  # not 'eLib' (a place), not 'A' or '_', not the Calibre book folders, not 'Extras', not the empty 'Poetry'
    assert left(result) == set(found(result)) - {"Banks, Iain M."}


def test_loose_books_in_a_fiction_genre_full_of_authors_leave_it_a_genre(lib):
    """'800 - Fiction/Fantasy' on the share: one loose PDF next to 306 author folders made Fantasy the author and every
    author a series (Erlend, 2026-11-21: the rule is for fiction)."""
    fantasy = lib / "800 - Fiction" / "Fantasy"
    touch(fantasy / "100 Must-Read Fantasy Novels.pdf")
    touch(fantasy / "Abbey, Lynn (1948-)" / "Lynn Abbey - Siege of Shadows.epub")
    touch(fantasy / "Akers, Tim (1972-)" / "Tim Akers - The Pagan Night.epub")
    touch(fantasy / "Anthony, Mark (1966-)" / "Last Rune" / "Mark Anthony - Beyond the Pale.epub")
    result = books.scan([lib / "800 - Fiction"])
    assert found(result) == {
        "Fantasy": "genre", "800 - Fiction": "genre", "Abbey, Lynn (1948-)": "author", "Akers, Tim (1972-)": "author",
        "Anthony, Mark (1966-)": "author", "Last Rune": "series"}


def test_loose_books_above_sub_genres_full_of_authors_leave_both_genres(lib):
    """'800 - Fiction/LitRPG' on the share: 39 loose new books next to sub-genres (Isekai, Cozy ...) that hold authors and
    a few loose books of their own."""
    litrpg = lib / "LitRPG"
    touch(litrpg / "Axel Halden - Reborn as a Dungeon Looter 1.epub")
    touch(litrpg / "Isekai" / "Loose One.epub")
    touch(litrpg / "Isekai" / "Ames, Vira" / "Vira Ames - Book.epub")
    touch(litrpg / "Isekai" / "Armand, Quinley" / "Quinley Armand - Book.epub")
    touch(litrpg / "Cozy" / "Cole, Luke" / "Luke Cole - Book.epub")  # on the share: 16 of Cozy's 19 folders have a comma
    touch(litrpg / "Cozy" / "Hale, Ada" / "Ada Hale - Book.epub")
    touch(litrpg / "Cozy" / "Blastix" / "Blastix - Book.epub")  # a pen name without a comma: books directly, the author
    assert found(books.scan([litrpg])) == {
        "LitRPG": "genre", "Isekai": "genre", "Cozy": "genre", "Ames, Vira": "author", "Armand, Quinley": "author",
        "Cole, Luke": "author", "Hale, Ada": "author", "Blastix": "author"}


def test_loose_books_next_to_subject_folders_still_make_an_author_or_shelf(lib):
    """Non-fiction: subject folders carry no author names, so a folder with loose books stays as it was."""
    touch(lib / "Physics" / "Feynman - Lectures.pdf")
    touch(lib / "Physics" / "Quantum" / "Some Book.pdf")
    assert found(books.scan([lib / "Physics"])) == {"Physics": "author", "Quantum": "series"}


def test_an_author_with_a_few_books_loose_and_series_folders_is_still_an_author(lib):
    author = lib / "Fantasy" / "Pratchett, Terry"
    touch(author / "Terry Pratchett - Good Omens.epub")
    touch(author / "Discworld" / "Terry Pratchett - Mort.epub")
    assert found(books.scan([lib / "Fantasy"]))["Pratchett, Terry"] == "author"


def test_looks_like_author():
    assert books.looks_like_author("Le Guin, Ursula K.") and not books.looks_like_author("813 - Fiction, American")
    assert not books.looks_like_author("Plato") and not books.looks_like_author("Banks,")


# -- the guess and the window -------------------------------------------------------------------------------------------

def test_the_media_guess_tells_books_and_comics_apart_and_guess_media_still_says_music_or_video(lib):
    assert guess_kind(books_tree(lib)) == BOOKS
    assert guess_kind(comics_tree(lib)) == COMICS
    touch(lib / "Music" / "Band" / "Album" / "01.mp3")
    assert guess_kind(lib / "Music") == MUSIC
    assert guess_media(lib / "eLib") == ""  # the command line and Look Up's library guess: music or video only


def test_the_tree_opens_and_lights_a_folder_whose_name_ends_in_a_dot(window, lib):
    author = lib / "Tolkien, J.R.R."
    touch(author / "author.md", "# Tolkien\n")
    touch(author / "Middle-earth" / "The Hobbit.epub")
    open_library(window, lib)
    pump(lambda: window.tree.state_known(str(author)), "the author's light")
    assert window.tree.note_state(str(author))[0] is not None  # the note is found, not 'no note'
    assert window.tree.select(author / "Middle-earth")  # its children can be listed


def test_scan_in_the_window_on_a_comics_tree_and_look_up_says_not_yet(window, lib):
    root = comics_tree(lib)
    open_library(window, lib)
    select(window, root)
    window.actions_by_key["scan_notes"].trigger()
    pump(lambda: not window._scan_running, "the scan")
    us = root / "5973 - US"
    assert window.tree.item_for(us / "M" / "3 - Marvel (1961-2012)" / "Spider-Man (1963-)") is not None
    assert window.tree.count_label(str(root)) == "7 left" and window.tree.count_label(str(us / "M")) == "3 left"
    assert window.progress_label.text() == "Scanned 741.59 - Comic Books: 7 left without a note, 2 have a note."
    window.actions_by_key["look_up"].trigger()
    assert "Look Up for comics is not built yet" in window.status_bar.currentMessage()
