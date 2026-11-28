"""
core/booknotes/local.py

What a book folder says by itself, before anything is looked up. Qt-free, no network.

  author_name(folder_name)    'Banks, Iain M.' -> 'Iain M. Banks' (life years and counts in brackets dropped)
  series_title(folder_name)   '02 - Culture (10 books)' -> 'Culture'
  genre_title(folder_name)    '813 - Fantasy' -> 'Fantasy' (the numbering is music's lookup_name rule)
  read_books(folder)          the books lying directly in a folder: title, series, number, year, from each EPUB's own OPF
                              (a Calibre metadata.opf beside it counts too), else from the file name

Reading an EPUB opens the zip and reads two small files (container.xml and the OPF), never the book's text. At most
MAX_BOOKS_READ books are opened per folder: an author folder over a network share can hold hundreds.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.books import BOOK_EXTENSIONS, CALIBRE_OPF, looks_like_author
from core.music.local import lookup_name
from core.shelf_scan import entries, literal

MAX_BOOKS_READ = 40
MAX_OPF_BYTES = 512 * 1024  # an OPF is a few kB; anything this big is not one

_BRACKETS = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")  # '(1954-2013)', '(10 books)', '[Calibre]' at the end
_NUMBERING = re.compile(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]+)\s*[-.)_]\s*")  # '02 - ', '1. ', 'IV - '


@dataclass
class LocalBook:
    file: str
    title: str
    series: str = ""
    number: str = ""
    year: str = ""
    authors: list[str] = field(default_factory=list)
    description: str = ""


def _strip_brackets(name: str) -> str:
    previous = None
    text = name.strip()
    while text != previous:
        previous, text = text, _BRACKETS.sub("", text).strip()
    return text or name.strip()


def author_name(folder_name: str) -> str:
    """The author's name as it is written on a book: 'Le Guin, Ursula K.' -> 'Ursula K. Le Guin'; a name without a comma
    stays as it is. Brackets at the end ('(1954-2013)') are dropped."""
    text = _strip_brackets(folder_name)
    if looks_like_author(text):
        last, _, first = text.partition(",")
        return f"{first.strip()} {last.strip()}".strip()
    return text


def series_title(folder_name: str) -> str:
    """The series' name: numbering in front and brackets at the end dropped ('02 - Culture (10 books)' -> 'Culture')."""
    return _strip_brackets(_NUMBERING.sub("", folder_name.strip())) or folder_name.strip()


def genre_title(folder_name: str) -> str:
    return lookup_name(folder_name) or folder_name.strip()


def is_author_folder(folder: Path) -> bool:
    return looks_like_author(_strip_brackets(folder.name))


# ---- reading the books ----------------------------------------------------------------------------------------------

def _local(tag: object) -> str:
    return str(tag).rsplit("}", 1)[-1].lower() if isinstance(tag, str) else ""


def _number(text: str) -> str:
    """'3.0' -> '3', '2.5' stays."""
    text = (text or "").strip()
    try:
        value = float(text)
    except ValueError:
        return text
    return str(int(value)) if value.is_integer() else text


def parse_opf(data: bytes) -> Optional[dict]:
    """{title, series, number, year, authors, description} of an OPF package document, or None."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    if _local(root.tag) != "package":
        return None
    metadata = next((c for c in root if _local(c.tag) == "metadata"), None)
    if metadata is None:
        return None
    out = {"title": "", "series": "", "number": "", "year": "", "authors": [], "description": ""}
    ids: dict[str, ET.Element] = {}
    for child in metadata:
        name = _local(child.tag)
        text = (child.text or "").strip()
        if name == "title" and not out["title"]:
            out["title"] = text
        elif name == "creator" and text:
            role = next((v for k, v in child.attrib.items() if _local(k) == "role"), "")
            if role.lower() in ("", "aut"):
                out["authors"].append(text)
        elif name == "date" and not out["year"]:
            found = re.search(r"\b(1\d{3}|20\d{2})\b", text)
            out["year"] = found.group(1) if found else ""
        elif name == "description" and not out["description"]:
            out["description"] = text
        elif name == "meta":
            meta_name, prop = child.attrib.get("name", ""), child.attrib.get("property", "")
            if meta_name == "calibre:series":
                out["series"] = child.attrib.get("content", "").strip()
            elif meta_name == "calibre:series_index":
                out["number"] = _number(child.attrib.get("content", ""))
            elif prop == "belongs-to-collection" and not out["series"]:
                out["series"] = text
                if child.attrib.get("id"):
                    ids[child.attrib["id"]] = child
            elif prop == "group-position" and child.attrib.get("refines", "").lstrip("#") in ids and not out["number"]:
                out["number"] = _number(text)
    return out if out["title"] else None


def _opf_of_epub(path: str) -> Optional[bytes]:
    try:
        with zipfile.ZipFile(literal(path)) as book:
            container = ET.fromstring(book.read("META-INF/container.xml"))
            rootfile = next((e.attrib.get("full-path", "") for e in container.iter() if _local(e.tag) == "rootfile"), "")
            if not rootfile or book.getinfo(rootfile).file_size > MAX_OPF_BYTES:
                return None
            return book.read(rootfile)
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError, RuntimeError, ValueError):
        return None


def title_from_file_name(stem: str) -> str:
    """'Iain M. Banks - Consider Phlebas' -> 'Consider Phlebas'; '01 - Consider Phlebas' -> 'Consider Phlebas'."""
    text = _strip_brackets(stem.replace("_", " "))
    if " - " in text:
        text = text.rpartition(" - ")[2]
    return _NUMBERING.sub("", text).strip() or stem


def read_books(folder: Path, limit: int = MAX_BOOKS_READ) -> list[LocalBook]:
    """The books lying directly in `folder`, in file-name order. EPUBs are read from their own OPF (at most `limit` of
    them); other formats, and EPUBs past the limit, are known by their file name only. A Calibre metadata.opf beside a
    single book describes that book."""
    files, _dirs = entries(folder)
    books = sorted((f for f in files if os.path.splitext(f)[1].lower() in BOOK_EXTENSIONS), key=str.casefold)
    calibre = next((f for f in files if f.lower() == CALIBRE_OPF), "")
    out: list[LocalBook] = []
    opened = 0
    for name in books:
        data: Optional[bytes] = None
        if calibre and len(books) == 1:
            try:
                with open(literal(Path(folder) / calibre), "rb") as handle:
                    data = handle.read(MAX_OPF_BYTES)
            except OSError:
                data = None
        if data is None and name.lower().endswith((".epub", ".kepub")) and opened < limit:
            opened += 1
            data = _opf_of_epub(str(Path(folder) / name))
        info = parse_opf(data) if data else None
        if info:
            out.append(LocalBook(name, info["title"], info["series"], info["number"], info["year"], info["authors"],
                                 info["description"]))
        else:
            out.append(LocalBook(name, title_from_file_name(os.path.splitext(name)[0])))
    return out
