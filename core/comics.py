"""
core/comics.py

Which folders of a COMICS library get a note (Pluteus: docs/library-layout.md), for Notes > Scan for Notes. Folder structure
only; Look Up for comics (ComicInfo.xml, Comic Vine) is plan step 18 and not built yet.

  series    a folder that holds comic files (.cbz, .cbr, .cb7, .cbt) directly          -> series.md
            nothing below a series folder is judged (annuals or extras inside it belong to it)
  grouping  a folder above series folders: publisher, lineage ('3.23 - Imprint'), country, continent, an underscore
            grouping ('_Crossovers')                                                     -> about.md
  no note   letter buckets (A, B-C, 0-9), a folder named only '_' (an attention marker), a folder with no comics below
            it, and the folder the scan starts from when its name is a place ('Comics', '741.59 - Comic Books')
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from core.shelf_scan import Callback, Recorder, ShelfScan, entries, has_extension, is_note_free_name, is_place_name, roots_of

COMIC_EXTENSIONS = frozenset({".cbz", ".cbr", ".cb7", ".cbt"})
KIND_SERIES = "series"
KIND_GROUPING = "grouping"
ALL_KINDS = (KIND_SERIES, KIND_GROUPING)


def scan(paths: Iterable, include_subfolders: bool = True, kinds: Iterable[str] = ALL_KINDS, include_outdated: bool = False,
         on_folder: Callback = None) -> ShelfScan:
    """The series and grouping folders under `paths` that have no note yet (`targets`) and those that have one (`skipped`).
    `include_subfolders` and `include_outdated` are accepted for the window's sake (it calls every media's scan alike) and
    change nothing: the scan always goes down (a grouping is only known from what is below it), and no comic notes are
    written by this program yet, so none is outdated.
    `on_folder(folder)` is called for every folder walked into (it may raise to stop the scan)."""
    record = Recorder(kinds)
    roots, record.result.missing = roots_of(paths)

    def walk(folder: Path, is_root: bool) -> bool:
        """Judges `folder` and below; True when comics are in it or below it."""
        if on_folder is not None:
            on_folder(folder)
        files, dirs = entries(folder)
        if has_extension(files, COMIC_EXTENSIONS):
            record.consider(folder, KIND_SERIES)
            return True
        below = False
        for child in dirs:
            below = walk(child, False) or below
        if below and not is_note_free_name(folder.name) and not (is_root and is_place_name(folder.name)):
            record.consider(folder, KIND_GROUPING)
        return below

    for root in roots:
        walk(root, True)
    return record.result
