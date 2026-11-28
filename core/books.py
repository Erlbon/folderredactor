"""
core/books.py

Which folders of a BOOKS library get a note (Pluteus: docs/library-layout.md, Genre/Sub-genre/Author), for Notes > Scan for
Notes and Look Up. Folder structure and names only; what the notes hold is core/booknotes (plan step 17).

  author   a folder named 'Surname, Given' (a comma in it) with books in it or below it, or else the first folder down
           that holds book files directly                                                -> author.md
  series   a folder inside an author folder that holds book files directly               -> series.md
  genre    a folder above author folders (genre, sub-genre)                              -> about.md
  no note  a Calibre book folder (book files beside a metadata.opf, inside an author: Calibre's Author/Title/ layout), a
           folder below a series, letter buckets (A, B-C), a folder named only '_', a folder with no books below it, and
           the folder the scan starts from when its name is a place ('Books', 'eLib')

Book files: EPUB first, and every other book format the library allows (Erlend, 2026-11-04: all formats, EPUB preferred),
PDF documents among them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.shelf_scan import Callback, Recorder, ShelfScan, entries, has_extension, is_note_free_name, is_place_name, roots_of

BOOK_EXTENSIONS = frozenset({".epub", ".kepub", ".pdf", ".mobi", ".azw", ".azw3", ".kfx", ".fb2", ".djvu", ".lit", ".pdb"})
CALIBRE_OPF = "metadata.opf"
KIND_AUTHOR = "author"
KIND_SERIES = "series"
KIND_GENRE = "genre"
ALL_KINDS = (KIND_AUTHOR, KIND_SERIES, KIND_GENRE)
NONE, BOOKS, CALIBRE = 0, 1, 2  # what a walked folder reports to the one above it


def looks_like_author(name: str) -> bool:
    """'Le Guin, Ursula K.' -- a comma between two names; not a numbered genre ('813 - Fiction, American')."""
    if "," not in name or name[:1].isdigit():
        return False
    last, _, first = name.partition(",")
    return bool(last.strip()) and bool(first.strip())


def _holds_authors(dirs: list[Path], depth: int = 2) -> bool:
    """Most of these folders are named like authors ('Le Guin, Ursula K.') or are sub-genres full of such folders
    ('LitRPG/Isekai'): their parent is a genre even with books lying loose in it (Erlend, 2026-11-21, for fiction:
    '800 - Fiction/Fantasy' with one loose PDF and 306 authors). Only author-named folders count, so non-fiction subject
    folders ('Physics', 'History') never trigger it."""
    if not dirs:
        return False
    authors = sum(looks_like_author(d.name) or (depth > 1 and _holds_authors(entries(d)[1], depth - 1)) for d in dirs)
    return authors * 2 > len(dirs)


def _is_calibre_book(files: list[str]) -> bool:
    return CALIBRE_OPF in {f.lower() for f in files} and has_extension(files, BOOK_EXTENSIONS)


def scan(paths: Iterable, include_subfolders: bool = True, kinds: Iterable[str] = ALL_KINDS, include_outdated: bool = False,
         on_folder: Callback = None) -> ShelfScan:
    """The author, series and genre folders under `paths` that have no note yet (`targets`) and those that have one
    (`skipped`). `include_subfolders` and `include_outdated` are accepted for the window's sake and change nothing (see
    core/comics.py). `on_folder(folder)` is called for every folder walked into (it may raise to stop the scan)."""
    record = Recorder(kinds)
    roots, record.result.missing = roots_of(paths)

    def walk(folder: Path, is_root: bool, in_author: bool, in_series: bool) -> int:
        """Judges `folder` and below: NONE (no books), BOOKS, or CALIBRE (a Calibre book folder: its parent decides)."""
        if on_folder is not None:
            on_folder(folder)
        files, dirs = entries(folder)
        direct = has_extension(files, BOOK_EXTENSIONS)
        if direct and _is_calibre_book(files):
            # Calibre's Author/Title (id)/: a folder per book, no note; the folder above is the author
            return BOOKS if in_author else CALIBRE
        if in_series:
            found = [walk(child, False, True, True) for child in dirs]
            return BOOKS if direct or any(found) else NONE
        if direct and not in_author and _holds_authors(dirs):
            direct = False  # loose books in a genre folder ('Fantasy/100 Must-Read Fantasy Novels.pdf'): left out, no note
        if direct:
            kind = KIND_SERIES if in_author else KIND_AUTHOR
            record.consider(folder, kind)
            for child in dirs:
                walk(child, False, True, kind == KIND_SERIES)
            return BOOKS
        is_author = not in_author and looks_like_author(folder.name)
        found = [walk(child, False, in_author or is_author, False) for child in dirs]
        if not any(found):
            return NONE
        if not in_author and not is_author and CALIBRE in found:
            is_author = True  # Calibre's layout, the author's name without a comma
        if is_author:
            record.consider(folder, KIND_AUTHOR)
        elif not in_author and not is_note_free_name(folder.name) and not (is_root and is_place_name(folder.name)):
            record.consider(folder, KIND_GENRE)
        return BOOKS

    for root in roots:
        walk(root, True, False, False)
    return record.result
