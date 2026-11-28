"""
core/comics.py

Which folders of a COMICS library get a note (Pluteus: docs/library-layout.md), for Notes > Scan for Notes and Look Up.
Folder structure only; what the notes hold is core/comicnotes (plan step 18).

  series    a folder that holds comic files (.cbz, .cbr, .cb7, .cbt) directly          -> series.md
            nothing below a series folder is judged (annuals or extras inside it belong to it)
            except: an underscore folder, or a folder whose folders are mostly groupings, stays a grouping even with
            comics lying loose in it; those loose comics get no note (2026-11-21); and so does a folder with loose
            comics AND folders of comics when most of the folders beside it are groupings ('594971 - Serbian' among
            the other countries; Erlend's B, 2026-11-21)
            also a series: a magazine run split by year, a folder whose folders are mostly year folders ('1943',
            '1943 (35 issues)', '2015 (52 Issues)': 'Robbedoes (1938-2005)', 'Diabolik'); the year folders get no note
            (Erlend's A, 2026-11-21)
  grouping  a folder above series folders: publisher, lineage ('3.23 - Imprint'), country, continent, an underscore
            grouping ('_Crossovers')                                                     -> about.md
  no note   letter buckets (A, B-C, 0-9), a folder named only '_' (an attention marker), a folder with no comics below
            it, and the folder the scan starts from when its name is a place ('Comics', '741.59 - Comic Books')
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from core.shelf_scan import Callback, Recorder, ShelfScan, entries, has_extension, is_note_free_name, is_place_name, roots_of

COMIC_EXTENSIONS = frozenset({".cbz", ".cbr", ".cb7", ".cbt"})
KIND_SERIES = "series"
KIND_GROUPING = "grouping"
ALL_KINDS = (KIND_SERIES, KIND_GROUPING)


def _is_underscore_grouping(name: str) -> bool:
    """'_Egmont', '_Crossovers': a grouping by the person's own mark, never a series. A folder named only '_' is not one."""
    return name.startswith("_") and bool(name.strip("_").strip())


_YEAR_FOLDER = re.compile(r"^(19|20)\d\d(\s*\([^)]*\))?$")  # '1943', '1943 (35 issues)', '2001 (50+2 issues)'


def _is_year_run(dirs: list[Path]) -> bool:
    """Most of these folders are year folders: a magazine run split by year ('Robbedoes (1938-2005)/1943 (35 issues)',
    '2000 AD (2000-)/2001 (50+2 issues)'). The folder holding them is one series; the years get no note (Erlend's A,
    2026-11-21)."""
    return bool(dirs) and sum(bool(_YEAR_FOLDER.match(d.name)) for d in dirs) * 2 > len(dirs)


def _comics_below(folder: Path, depth: int) -> bool:
    files, dirs = entries(folder)
    return has_extension(files, COMIC_EXTENSIONS) or (depth > 1 and any(_comics_below(d, depth - 1) for d in dirs))


def _holds_groupings(dirs: list[Path]) -> bool:
    """Most of these folders are underscore groupings, or folders of series (no comics of their own, comics below them)."""
    if not dirs:
        return False
    count = 0
    for d in dirs:
        if _is_underscore_grouping(d.name):
            count += 1
            continue
        files, inner = entries(d)
        if (not has_extension(files, COMIC_EXTENSIONS) and not _is_year_run(inner)
                and any(_comics_below(i, 3) for i in inner)):
            count += 1
    return count * 2 > len(dirs)


def _grouping_with_loose_comics(folder: Path, dirs: list[Path]) -> bool:
    """A folder with comic files lying loose in it that is still a grouping, not a series (Erlend, 2026-11-21, from the
    share: '594 - EU/59481 - Norwegian' holds six loose albums next to '_Egmont', '_Semic' ...; '_Egmont' holds loose Kid
    Paddle albums next to its 'Nemi' series): an underscore folder, or one whose folders are mostly groupings. Its loose
    comics get no note. A series with an 'Annuals' folder of comics stays one series."""
    return _is_underscore_grouping(folder.name) or _holds_groupings(dirs)


SIBLINGS_NEEDED = 3  # folders beside one before what they are counts as a pattern


def _looks_like_grouping(folder: Path) -> bool:
    """A grouping by its own contents: an underscore folder, a folder of series (no comics of its own, comics below), or one
    with loose comics whose folders are mostly groupings. (Not by its siblings: that would go round in circles.)"""
    if _is_underscore_grouping(folder.name):
        return True
    files, dirs = entries(folder)
    if not has_extension(files, COMIC_EXTENSIONS):
        return not _is_year_run(dirs) and any(_comics_below(d, 3) for d in dirs)
    return _holds_groupings(dirs)


def scan(paths: Iterable, include_subfolders: bool = True, kinds: Iterable[str] = ALL_KINDS, include_outdated: bool = False,
         on_folder: Callback = None) -> ShelfScan:
    """The series and grouping folders under `paths` that have no note yet (`targets`) and those that have one (`skipped`).
    `include_subfolders` and `include_outdated` are accepted for the window's sake (it calls every media's scan alike) and
    change nothing: the scan always goes down (a grouping is only known from what is below it), and no comic notes are
    written by this program yet, so none is outdated.
    `on_folder(folder)` is called for every folder walked into (it may raise to stop the scan)."""
    record = Recorder(kinds)
    roots, record.result.missing = roots_of(paths)
    grouping_children: dict[str, dict[str, bool]] = {}  # parent folder -> {child name: looks like a grouping}

    def siblings_are_groupings(folder: Path) -> bool:
        """Most of the other folders beside `folder` are groupings ('594 - EU/594971 - Serbian' beside the other countries).
        Worked out once per parent folder."""
        parent = folder.parent
        if parent == folder:
            return False
        key = str(parent)
        if key not in grouping_children:
            grouping_children[key] = {d.name: _looks_like_grouping(d) for d in entries(parent)[1]}
        others = [v for name, v in grouping_children[key].items() if name != folder.name]
        # at least three others, or one '_Crossovers' beside 'Spider-Man (1963-)/Annuals' would make the series a grouping
        return len(others) >= SIBLINGS_NEEDED and sum(others) * 2 > len(others)

    def walk(folder: Path, is_root: bool) -> bool:
        """Judges `folder` and below; True when comics are in it or below it."""
        if on_folder is not None:
            on_folder(folder)
        files, dirs = entries(folder)
        loose = has_extension(files, COMIC_EXTENSIONS)
        # a series with one 'Hors série' / 'Annuals' folder stays a series, whatever is beside it; a country with loose
        # albums next to two or more folders of comics follows the countries beside it
        if loose and not _grouping_with_loose_comics(folder, dirs) and not (
                sum(_comics_below(d, 3) for d in dirs) >= 2 and siblings_are_groupings(folder)):
            record.consider(folder, KIND_SERIES)
            return True
        # a magazine run split by year folders is one series; nothing below it is judged
        if not loose and _is_year_run(dirs) and any(_comics_below(d, 2) for d in dirs):
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
