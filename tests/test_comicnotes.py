"""Comics notes (core/comicnotes, plan step 18; Erlend's D32, D34-D36, 2026-11-21, with D33 changed the same day to the
comics' own ComicInfo.xml and the folder names only): names and years from folders, ComicInfo.xml from the CBZs, the
album list, and Wikipedia for groupings. Every tree is built in tmp_path; the network is FakeFetch."""

import zipfile
from pathlib import Path

import pytest

from core.comicnotes import local, render
from core.comicnotes import settings as comic_settings
from core.comicnotes.flow import Fetchers, NotesEngine, scan
from core.shelf_scan import Target
from redactor_common.core.notes_model import Confidence
from tests.video_helpers import FakeFetch

COMICINFO = """<?xml version="1.0"?>
<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Series>Asterix</Series><Number>{number}</Number><Title>{title}</Title><Year>{year}</Year><Count>{count}</Count>
  <Summary>The plot of this one album only.</Summary>
  <Writer>René Goscinny</Writer><Penciller>Albert Uderzo</Penciller>
  <Publisher>Dargaud</Publisher><Genre>Humour, Adventure</Genre>
</ComicInfo>"""


def cbz(path: Path, title: str = "", number: str = "1", year: str = "1961", count: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as comic:
        comic.writestr("001.jpg", b"not a picture")
        if title:
            comic.writestr("ComicInfo.xml", COMICINFO.format(title=title, number=number, year=year, count=count))
    return path


def bare(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def page(title: str, extract: str, lang: str = "en") -> dict:
    return {"title": title, "extract": extract, "description": "", "type": "standard",
            "content_urls": {"desktop": {"page": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"}}}


def engine(routes=(), wikipedia=True) -> NotesEngine:
    return NotesEngine(Fetchers(wiki=FakeFetch(list(routes) + [(r"search/title", {"pages": []})]), wikipedia=wikipedia))


# -- names, years, languages ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("folder, title, years", [
    ("_Dupuis (1922-)", "Dupuis", "1922-"), ("5944 - French", "French", ""), ("Asterix (1961-)", "Asterix", "1961-"),
    ("Robbedoes (1938-2005)", "Robbedoes", "1938-2005"), ("3 - Marvel (1961-2012)", "Marvel", "1961-2012"),
    ("2000 AD (2000-)", "2000 AD", "2000-"), ("_Crossovers", "Crossovers", ""),
])
def test_title_and_years_from_the_folder(folder, title, years):
    assert local.folder_title(folder) == title
    assert local.folder_years(folder) == years


def test_the_country_folder_gives_the_languages(tmp_path):
    assert local.country_languages(tmp_path / "594 - EU" / "59493 - Belgian" / "_Dupuis (1922-)") == ("fr", "nl")
    assert local.country_languages(tmp_path / "594 - EU" / "59481 - Norwegian" / "_Egmont") == ("no",)
    assert local.country_languages(tmp_path / "5973 - US" / "3 - Marvel (1961-2012)") == ()


@pytest.mark.parametrize("stem, number, title, year", [
    ("Asterix 01 - Asterix le Gaulois (1961)", "1", "Asterix le Gaulois", "1961"),
    ("Asterix le Gaulois", "", "Asterix le Gaulois", ""),
    ("T03 - La Serpe d'or", "3", "La Serpe d'or", ""),
    ("Asterix #12", "12", "", ""),
])
def test_album_from_the_file_name(stem, number, title, year):
    album = local.album_from_file_name(stem, "Asterix")
    assert (album.number, album.title, album.year) == (number, title, year)


def test_comicinfo_gives_number_title_year_credits_and_publisher(tmp_path):
    folder = tmp_path / "Asterix (1961-)"
    cbz(folder / "b.cbz", "Asterix and the Golden Sickle", "2", "1962")
    cbz(folder / "a.cbz", "Asterix the Gaul", "1", "1961")
    bad = folder / "c.cbz"
    bad.write_bytes(b"not a zip")
    bare(folder / "Asterix 03 - Asterix and the Goths (1963).cbr")
    found = local.read_albums(folder, series="Asterix")
    assert [(a.number, a.title, a.year) for a in found.albums] == [
        ("1", "Asterix the Gaul", "1961"), ("2", "Asterix and the Golden Sickle", "1962"),
        ("3", "Asterix and the Goths", "1963"), ("", "c", "")]
    assert found.with_comicinfo == 2 and found.publisher == "Dargaud"
    assert ("Writer", "René Goscinny") in found.credits and ("Artist", "Albert Uderzo") in found.credits
    assert found.genres == ["Humour", "Adventure"] and (found.first_year, found.last_year) == ("1961", "1963")


# -- series notes -----------------------------------------------------------------------------------------------------

def test_series_note_from_comicinfo_with_the_album_list(tmp_path):
    folder = tmp_path / "Asterix (1961-)"
    cbz(folder / "02.cbz", "Asterix and the Golden Sickle", "2", "1962")
    cbz(folder / "01.cbz", "Asterix the Gaul", "1", "1961")
    p = engine().build_proposal(Target(folder, "series"))
    assert p.confidence == Confidence.CONFIDENT
    text = p.note_text
    assert "title: Asterix" in text and "years: 1961-" in text and "status: draft" in text
    assert "**Writer:** René Goscinny" in text and "**Publisher:** Dargaud" in text
    assert text.index("## Albums") < text.index("- 1. Asterix the Gaul (1961)") < \
        text.index("- 2. Asterix and the Golden Sickle (1962)")
    assert "plot of this one album" not in text  # ComicInfo's Summary is one album's, never the series'
    assert render.COMICINFO_CREDIT in text


def test_series_without_comicinfo_is_built_from_file_names_and_uncertain(tmp_path):
    folder = tmp_path / "Blake et Mortimer"
    bare(folder / "Blake et Mortimer 01 - Le Secret de l'Espadon (1950).cbr")
    p = engine().build_proposal(Target(folder, "series"))
    assert p.confidence == Confidence.UNCERTAIN
    assert "- 1. Le Secret de l'Espadon (1950)" in p.note_text and render.FILE_NAMES_CREDIT in p.note_text
    assert any("not of the whole series" in r for r in p.reasons)


def test_a_long_series_gets_no_album_list(tmp_path):
    folder = tmp_path / "Lucky Luke (1949-)"
    cbz(folder / "01.cbz", "Arizona", "1", "1951", count="120")  # ComicInfo says the series has 120 albums
    p = engine().build_proposal(Target(folder, "series"))
    assert "## Albums" not in p.note_text and "Arizona" not in p.note_text
    assert any("no album list" in r for r in p.reasons)


def test_a_run_split_by_year_is_one_series_without_a_list(tmp_path):
    folder = tmp_path / "Robbedoes (1938-2005)"
    cbz(folder / "1943 (35 issues)" / "001.cbz", "Robbedoes 1", "1", "1943")
    bare(folder / "1944" / "001.cbr")
    p = engine().build_proposal(Target(folder, "series"))
    assert p.confidence == Confidence.CONFIDENT
    assert "years: 1938-2005" in p.note_text and "## Albums" not in p.note_text
    assert "**Writer:** René Goscinny" in p.note_text  # the credits of the first year's comics


# -- grouping notes ---------------------------------------------------------------------------------------------------

def test_publisher_grouping_gets_the_english_paragraph(tmp_path):
    folder = tmp_path / "5973 - US" / "3 - Marvel (1961-2012)"
    folder.mkdir(parents=True)
    wiki = [(r"en\.wikipedia.*summary/Marvel_Comics", page("Marvel Comics", "Marvel Comics is an American comic book publisher."))]
    p = engine(wiki).build_proposal(Target(folder, "grouping"))
    text = p.note_text
    assert p.confidence == Confidence.CONFIDENT and p.sources == ["Wikipedia"]
    assert "title: Marvel" in text and "years: 1961-2012" in text and "American comic book publisher" in text
    assert "en.wikipedia.org/wiki/Marvel_Comics" in text


def test_grouping_falls_back_to_the_country_folders_language(tmp_path):
    folder = tmp_path / "594 - EU" / "59493 - Belgian" / "_Dupuis (1922-)"
    folder.mkdir(parents=True)
    fetch = FakeFetch([(r"en\.wikipedia", None),
                       (r"fr\.wikipedia.*summary/Dupuis", page("Dupuis", "Dupuis est une maison d'édition belge de bande "
                                                                         "dessinée.", "fr"))])
    p = NotesEngine(Fetchers(wiki=fetch)).build_proposal(Target(folder, "grouping"))
    assert "maison d'édition belge" in p.note_text and "fr.wikipedia.org" in p.note_text
    assert "years: 1922-" in p.note_text and any("(fr)" in r for r in p.reasons)
    assert not fetch.asked(r"nl\.wikipedia")  # French found first: Dutch never asked


def test_a_page_that_is_not_about_comics_is_not_used(tmp_path):
    folder = tmp_path / "_Semic"
    folder.mkdir()
    p = engine([(r"summary/Semic$", page("Semic", "Semic is a village in Poland."))]).build_proposal(
        Target(folder, "grouping"))
    assert "village" not in p.note_text and "# Semic" in p.note_text  # D35A: title only
    assert p.sources == ["the folder name"]


def test_grouping_without_wikipedia_is_title_and_years_only(tmp_path):
    folder = tmp_path / "_Dupuis (1922-)"
    folder.mkdir()
    fetch = FakeFetch()
    p = NotesEngine(Fetchers(wiki=fetch, wikipedia=False)).build_proposal(Target(folder, "grouping"))
    assert "# Dupuis" in p.note_text and "years: 1922-" in p.note_text and fetch.urls == []


# -- scan, minimal note, settings -------------------------------------------------------------------------------------

def test_look_up_on_one_folder_keeps_only_that_folder(tmp_path):
    publisher = tmp_path / "Comics" / "_Dargaud"
    bare(publisher / "Asterix" / "01.cbz")
    bare(publisher / "Blueberry" / "01.cbz")
    assert [t.folder.name for t in scan([publisher / "Asterix"], include_subfolders=False).targets] == ["Asterix"]
    assert {t.folder.name for t in scan([publisher], include_subfolders=True).targets} == {"_Dargaud", "Asterix", "Blueberry"}


def test_minimal_note_from_the_folder_name(tmp_path):
    folder = tmp_path / "Asterix (1961-)"
    bare(folder / "01.cbz")
    e = engine()
    p = e.local_note(e.build_proposal(Target(folder, "series")))
    assert "# Asterix" in p.note_text and "years: 1961-" in p.note_text and render.LOCAL_ONLY_CREDIT in p.note_text


def test_the_kinds_setting_reads_words_and_falls_back_to_all():
    assert comic_settings.parse_kinds("grouping") == ("grouping",)
    assert comic_settings.parse_kinds("publishers, series") == ("series", "grouping")
    assert comic_settings.parse_kinds("nonsense") == ("series", "grouping")
