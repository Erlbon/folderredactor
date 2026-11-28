"""
core/comicnotes/local.py

What a comics folder says by itself (Erlend, 2026-11-21: comics notes come from the comics' own ComicInfo.xml and the
folder names only; no Comic Vine, no Bedetheque). Qt-free, no network.

  folder_title(folder_name)    '_Dupuis (1922-)' -> 'Dupuis', '5944 - French' -> 'French', 'Asterix (1961-)' -> 'Asterix'
  folder_years(folder_name)    '(1922-)' -> '1922-', '(1938-2005)' -> '1938-2005', none -> ''
  read_albums(folder)          the comics lying directly in a folder: number, title, year from each CBZ's ComicInfo.xml,
                               else from the file name; the credits, publisher and genre of those that have one
  country_languages(path)      the Wikipedia languages of the country folder in a path ('5944 - French' -> ('fr',))

Only .cbz can be opened (a zip). .cbr and .cb7 are known by their file name only: reading them needs an unrar / 7-Zip
library this program does not carry. Reading a CBZ opens the zip's directory and one small file, never the pages. At most
MAX_COMICS_READ comics are opened per folder: a series over a network share can hold hundreds.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.comics import COMIC_EXTENSIONS
from core.music.local import lookup_name
from core.shelf_scan import entries, literal

MAX_COMICS_READ = 40
MAX_COMICINFO_BYTES = 256 * 1024  # a ComicInfo.xml is a few kB

_YEARS = re.compile(r"[(\[]\s*(\d{4})\s*[-–—]\s*(\d{4})?\s*[)\]]\s*$")
_BRACKETS_END = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")
_YEAR_IN_BRACKETS = re.compile(r"[(\[]\s*((?:19|20)\d\d)\s*[)\]]")
_LEADING_NUMBER = re.compile(r"^\s*(?:#|T|Tome\s*|Vol\.?\s*|Volume\s*|No\.?\s*)?(\d{1,4}(?:\.\d+)?)\b\s*[-.:_)]*\s*",
                             re.IGNORECASE)

CREDIT_TAGS = (("Writer", "Writer"), ("Penciller", "Artist"), ("Inker", "Inker"), ("Colorist", "Colours"),
               ("Letterer", "Letters"), ("CoverArtist", "Cover"))
MAX_NAMES_PER_CREDIT = 4

# the country folder's word -> the Wikipedia languages to try after English (D36B), the first that has a page wins
COUNTRY_LANGUAGES = {
    "french": ("fr",), "belgian": ("fr", "nl"), "swiss": ("fr", "de", "it"), "dutch": ("nl",), "flemish": ("nl",),
    "german": ("de",), "austrian": ("de",), "italian": ("it",), "spanish": ("es",), "catalan": ("ca", "es"),
    "portuguese": ("pt",), "brazilian": ("pt",), "norwegian": ("no",), "swedish": ("sv",), "danish": ("da",),
    "finnish": ("fi",), "icelandic": ("is",), "polish": ("pl",), "czech": ("cs",), "slovak": ("sk",),
    "hungarian": ("hu",), "serbian": ("sr",), "croatian": ("hr",), "slovenian": ("sl",), "greek": ("el",),
    "japanese": ("ja",), "korean": ("ko",), "chinese": ("zh",), "argentine": ("es",), "argentinian": ("es",),
    "mexican": ("es",), "russian": ("ru",), "turkish": ("tr",),
}


@dataclass
class Album:
    file: str
    title: str = ""
    number: str = ""
    year: str = ""


@dataclass
class FolderComics:
    """What the comics lying in one folder say: the albums in order, and from their ComicInfo.xml the most common
    publisher, genres and credits."""

    albums: list[Album] = field(default_factory=list)
    with_comicinfo: int = 0
    series_names: list[str] = field(default_factory=list)  # ComicInfo Series, most common first
    publisher: str = ""
    genres: list[str] = field(default_factory=list)
    credits: list[tuple[str, str]] = field(default_factory=list)  # (label, 'Name, Name')
    count: int = 0  # ComicInfo Count (albums in the whole series), 0 when none says
    first_year: str = ""
    last_year: str = ""


def folder_title(folder_name: str) -> str:
    """The name a comics folder stands for: a leading '_' (the person's grouping mark), numbering ('5944 - French',
    '3.23 - Imprint') and brackets at the end ('(1922-)', '(35 issues)') taken off."""
    text = (folder_name or "").strip().lstrip("_").strip()
    text = lookup_name(text) or text
    previous = None
    while text != previous:
        previous, text = text, _BRACKETS_END.sub("", text).strip()
    return text or (folder_name or "").strip()


def folder_years(folder_name: str) -> str:
    match = _YEARS.search((folder_name or "").strip())
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2) or ''}"


def country_languages(folder: Path) -> tuple[str, ...]:
    """The languages of the nearest country folder at or above `folder` ('.../5944 - French/_Dupuis' -> ('fr',)); () when
    the path has none (English only)."""
    for part in [folder, *folder.parents]:
        for word in re.findall(r"[a-z]+", folder_title(part.name).lower()):
            if word in COUNTRY_LANGUAGES:
                return COUNTRY_LANGUAGES[word]
    return ()


# ---- reading the comics -----------------------------------------------------------------------------------------

def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def parse_comicinfo(data: bytes) -> Optional[dict[str, str]]:
    """The fields of a ComicInfo.xml, by lower-case tag name, or None when it is not one."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    if _local(root.tag) != "comicinfo":
        return None
    return {_local(child.tag): (child.text or "").strip() for child in root if (child.text or "").strip()}


def _comicinfo_of_cbz(path: str) -> Optional[dict[str, str]]:
    try:
        with zipfile.ZipFile(literal(path)) as comic:
            name = next((n for n in comic.namelist() if n.rsplit("/", 1)[-1].lower() == "comicinfo.xml"), "")
            if not name or comic.getinfo(name).file_size > MAX_COMICINFO_BYTES:
                return None
            return parse_comicinfo(comic.read(name))
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError):
        return None


def album_from_file_name(stem: str, series: str = "") -> Album:
    """'Asterix 01 - Asterix le Gaulois (1961)' -> number '1', title 'Asterix le Gaulois', year '1961'. The series' own
    name in front is dropped; a name that is only the series and a number keeps no title."""
    text = stem.replace("_", " ").strip()
    year_match = _YEAR_IN_BRACKETS.search(text)
    year = year_match.group(1) if year_match else ""
    previous = None
    while text != previous:
        previous, text = text, _BRACKETS_END.sub("", text).strip()
    if series and text.casefold().startswith(series.casefold()):
        rest = text[len(series):]
        # only the series' name in front of a number or a dash: 'Asterix le Gaulois' keeps its 'Asterix'
        if _LEADING_NUMBER.match(rest.strip()) or rest.lstrip().startswith(("-", "–", ":")):
            text = rest.strip(" -–.:,")
    number = ""
    match = _LEADING_NUMBER.match(text)
    if match:
        number, text = _number(match.group(1)), text[match.end():].strip(" -.:")
    return Album("", text, number, year)


def _number(text: str) -> str:
    """'01' -> '1', '3.0' -> '3', '2.5' stays, '1a' stays."""
    text = (text or "").strip()
    try:
        value = float(text)
    except ValueError:
        return text
    return str(int(value)) if value.is_integer() else text


def _year(text: str) -> str:
    match = re.search(r"\b(1[89]\d\d|20\d\d)\b", text or "")
    return match.group(1) if match else ""


def _sort_key(album: Album) -> tuple:
    try:
        return (0, float(album.number), album.file.casefold())
    except ValueError:
        return (1, 0.0, album.file.casefold())


def read_albums(folder: Path, limit: int = MAX_COMICS_READ, series: str = "") -> FolderComics:
    """The comics lying directly in `folder`, by number (those without one after, by file name). `series` is the folder's
    title, dropped from the front of file names."""
    files, _dirs = entries(folder)
    names = sorted((f for f in files if os.path.splitext(f)[1].lower() in COMIC_EXTENSIONS), key=str.casefold)
    out = FolderComics()
    series_names: Counter = Counter()
    publishers: Counter = Counter()
    genres: Counter = Counter()
    credits: dict[str, Counter] = {label: Counter() for _tag, label in CREDIT_TAGS}
    counts: Counter = Counter()
    years: list[str] = []
    opened = 0
    for name in names:
        stem, ext = os.path.splitext(name)
        album = album_from_file_name(stem, series)
        album.file = name
        info: Optional[dict[str, str]] = None
        if ext.lower() == ".cbz" and opened < limit:
            opened += 1
            info = _comicinfo_of_cbz(str(Path(folder) / name))
        if info:
            out.with_comicinfo += 1
            album.title = info.get("title", "") or album.title
            album.number = _number(info.get("number", "")) or album.number
            album.year = _year(info.get("year", "")) or album.year
            if info.get("series"):
                series_names[info["series"]] += 1
            if info.get("publisher"):
                publishers[info["publisher"]] += 1
            for genre in re.split(r"\s*[,;]\s*", info.get("genre", "")):
                if genre:
                    genres[genre] += 1
            for tag, label in CREDIT_TAGS:
                for person in re.split(r"\s*[,;]\s*", info.get(tag.lower(), "")):
                    if person:
                        credits[label][person] += 1
            if info.get("count", "").isdigit() and int(info["count"]) > 0:
                counts[int(info["count"])] += 1
        if album.year:
            years.append(album.year)
        out.albums.append(album)
    out.albums.sort(key=_sort_key)
    out.series_names = [s for s, _n in series_names.most_common()]
    out.publisher = publishers.most_common(1)[0][0] if publishers else ""
    out.genres = [g for g, _n in genres.most_common(5)]
    out.credits = [(label, ", ".join(p for p, _n in credits[label].most_common(MAX_NAMES_PER_CREDIT)))
                   for _tag, label in CREDIT_TAGS if credits[label]]
    out.count = counts.most_common(1)[0][0] if counts else 0
    if years:
        out.first_year, out.last_year = min(years), max(years)
    return out


def year_folders(folder: Path) -> list[Path]:
    """The year folders of a magazine run split by year ('1943 (35 issues)'), oldest first (core/comics.py's rule)."""
    from core.comics import _YEAR_FOLDER  # noqa: PLC0415 -- the one rule of what a year folder is

    return sorted((d for d in entries(folder)[1] if _YEAR_FOLDER.match(d.name)), key=lambda d: d.name)
